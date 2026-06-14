"""高勝率bot / 高ボラbot 固有ロジックのテスト。

実行: python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_winrate import WinRateScalper
from src.strategy_event import EventStrategy
from src.broker.paper import PaperBroker
from src.signals import Signal

JST = timezone(timedelta(hours=9))


class TestWinRateSessionFilter(unittest.TestCase):
    def test_out_of_session_blocks(self):
        cfg = {"winrate": {"sessions_jst": [[16, 26]]}}
        s = WinRateScalper(cfg)
        # 09:00 JST はセッション外 → 必ず None
        morning = datetime(2026, 6, 14, 9, 0, tzinfo=JST)
        self.assertIsNone(s.evaluate([157.0] * 200, morning))

    def test_in_session_allows_evaluation(self):
        # セッション内なら _in_session は True（実シグナル有無は別）
        s = WinRateScalper({"winrate": {"sessions_jst": [[16, 26]]}})
        evening = datetime(2026, 6, 14, 20, 0, tzinfo=JST)
        self.assertTrue(s._in_session(evening))
        past_midnight = datetime(2026, 6, 14, 1, 0, tzinfo=JST)
        self.assertTrue(s._in_session(past_midnight))  # 日跨ぎ 16〜26

    def test_none_session_is_24h(self):
        s = WinRateScalper({"winrate": {"sessions_jst": None}})
        self.assertTrue(s._in_session(datetime(2026, 6, 14, 4, 0, tzinfo=JST)))


class TestPaperTrailing(unittest.TestCase):
    def test_trailing_locks_profit_and_winrate(self):
        b = PaperBroker(spread_yen=0.0)
        sig = Signal(side="BUY", reason="test", price=150.0, lots=1.0, take_profit=None,
                     stop_loss=149.0, trail_distance=0.20)
        b.place_order(sig)
        # 価格上昇でトレーリングSLが切り上がる
        b.update_price(150.5)   # best=150.5, sl -> 150.30
        b.update_price(151.0)   # best=151.0, sl -> 150.80
        self.assertGreaterEqual(b.positions[0].sl, 150.79)
        # 押し戻しでトレーリングSLに当たり利益確定
        logs = b.update_price(150.70)
        self.assertTrue(any("決済" in x for x in logs))
        self.assertEqual(b.wins, 1)
        self.assertGreater(b.realized_pnl_yen, 0)
        self.assertEqual(b.win_rate(), 100.0)


class TestVolatilityBreakoutTrail(unittest.TestCase):
    def test_breakout_sets_trailing(self):
        ev = EventStrategy({"event": {"range_lookback": 20, "atr_period": 14,
                                      "breakout_buffer_atr": 0.0, "trail_atr": 1.0}})
        closes = [150.0 + (i % 2) * 0.05 for i in range(40)] + [150.6]
        sig = ev.breakout_signal(closes)
        self.assertIsNotNone(sig)
        self.assertIsNotNone(sig.trail_distance)
        self.assertGreater(sig.trail_distance, 0)


if __name__ == "__main__":
    unittest.main()
