"""指標と戦略の最小テスト（標準ライブラリ unittest）。

実行: python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.indicators import sma, ema, rsi, atr_from_closes, bollinger, rolling_high_low
from src.strategy_campaign import CampaignScalper
from src.strategy_event import EventStrategy, default_event_windows


class TestIndicators(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(sma([1], 2))

    def test_ema_monotonic_uptrend(self):
        vals = list(range(1, 60))
        e = ema(vals, 10)
        self.assertIsNotNone(e)
        self.assertLess(e, vals[-1])  # 上昇中は EMA < 現値

    def test_rsi_bounds(self):
        up = list(range(1, 50))
        self.assertGreater(rsi(up, 14), 90)  # 連続上昇 → 高 RSI
        down = list(range(50, 1, -1))
        self.assertLess(rsi(down, 14), 10)

    def test_atr_positive(self):
        vals = [100 + (i % 3) * 0.1 for i in range(30)]
        a = atr_from_closes(vals, 14)
        self.assertIsNotNone(a)
        self.assertGreater(a, 0)

    def test_bollinger(self):
        vals = [10] * 20
        mid, up, lo, sd = bollinger(vals, 20, 2)
        self.assertEqual(mid, 10)
        self.assertEqual(sd, 0)

    def test_rolling_high_low(self):
        hi, lo = rolling_high_low([1, 5, 3, 2, 8, 4], 4)
        self.assertEqual(hi, 8)
        self.assertEqual(lo, 2)


class TestCampaignStrategy(unittest.TestCase):
    def test_oversold_triggers_buy(self):
        cfg = {"campaign": {"ema_period": 20, "rsi_period": 14, "atr_period": 14,
                            "entry_dev_atr": 0.5, "min_atr": 0.0, "max_atr": 999}}
        scalper = CampaignScalper(cfg)
        # 上げてから急落 → 下方乖離 & 低RSI を作る
        closes = [100 + i * 0.1 for i in range(40)] + [104 - i * 0.5 for i in range(15)]
        sig = scalper.evaluate(closes)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "BUY")
        self.assertIsNotNone(sig.stop_loss)
        self.assertIsNotNone(sig.take_profit)


class TestEventStrategy(unittest.TestCase):
    def test_windows_dates(self):
        ws = default_event_windows(2026)
        names = " ".join(w.name for w in ws)
        self.assertIn("BOJ", names)
        self.assertIn("FOMC", names)
        # BOJ は 6/16、FOMC窓は 6/18 早朝(JST)
        boj = next(w for w in ws if "BOJ" in w.name)
        fomc = next(w for w in ws if "FOMC" in w.name)
        self.assertEqual((boj.start.month, boj.start.day), (6, 16))
        self.assertEqual((fomc.start.month, fomc.start.day), (6, 18))

    def test_intervention_signal(self):
        cfg = {"event": {"intervention_watch_level": 160.0, "spike_lookback": 5,
                         "spike_threshold_yen": 1.0, "atr_period": 14}}
        ev = EventStrategy(cfg)
        # 直近5本で 158.6→159.8 へ +1.2円 急騰（現足が高値）→ 介入警戒の売りシグナル
        closes = [158.0] * 20 + [158.6, 158.9, 159.2, 159.5, 159.8]
        sig = ev.intervention_signal(closes)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "SELL")
        self.assertEqual(sig.urgency, "high")

    def test_breakout_up(self):
        cfg = {"event": {"range_lookback": 20, "atr_period": 14, "breakout_buffer_atr": 0.0}}
        ev = EventStrategy(cfg)
        closes = [150.0 + (i % 2) * 0.05 for i in range(40)] + [150.5]
        sig = ev.breakout_signal(closes)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.side, "BUY")


if __name__ == "__main__":
    unittest.main()
