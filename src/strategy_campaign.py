"""キャンペーン消化（90lot）向け 低リスク・スキャルプ戦略。

■ 思想（最重要）
  みんなのFXのキャッシュバックは「90lot の新規取引を完了」した時点で確定する。
  つまり"勝率を最大化して相場で稼ぐ"必要は無く、
  "スプレッド/スリッページの出費を最小化しつつ 90lot を淡々と消化"するのが期待値最大。
  本戦略は方向性の賭けを小さく保ち、ロット消化を主目的に、わずかな逆張りエッジを乗せる。

■ ロジック（平均回帰スキャルプ）
  - EMA からの乖離が k*ATR を超え、かつ RSI が行き過ぎ → 中心回帰方向へエントリー。
  - TP は浅く（tp_atr*ATR）、SL はやや広め（sl_atr*ATR）だが size を小さく固定。
  - 高ボラ（イベント窓）では稼働しない。イベントは strategy_event 側に任せる。

注意: これは"低リスクで確実にロットを消化する"設計であり、相場で大きく勝つ設計ではない。
"""

from __future__ import annotations

from typing import List, Optional

from .indicators import ema, rsi, atr_from_closes
from .signals import Signal


class CampaignScalper:
    def __init__(self, cfg: dict) -> None:
        c = (cfg.get("campaign") or {})
        self.ema_period = int(c.get("ema_period", 50))
        self.rsi_period = int(c.get("rsi_period", 14))
        self.atr_period = int(c.get("atr_period", 14))
        self.dev_atr = float(c.get("entry_dev_atr", 1.2))   # 乖離しきい値（ATR 倍）
        self.rsi_low = float(c.get("rsi_low", 30.0))
        self.rsi_high = float(c.get("rsi_high", 70.0))
        self.tp_atr = float(c.get("tp_atr", 0.6))
        self.sl_atr = float(c.get("sl_atr", 1.0))
        self.lots = float(c.get("lots_per_trade", 1.0))
        self.min_atr = float(c.get("min_atr", 0.005))       # 無風すぎる時は見送り
        self.max_atr = float(c.get("max_atr", 0.20))        # 荒れすぎは見送り（イベント側へ）

    def evaluate(self, closes: List[float]) -> Optional[Signal]:
        if len(closes) < max(self.ema_period, self.rsi_period, self.atr_period) + 2:
            return None
        price = closes[-1]
        e = ema(closes, self.ema_period)
        r = rsi(closes, self.rsi_period)
        a = atr_from_closes(closes, self.atr_period)
        if e is None or r is None or a is None or a <= 0:
            return None
        if a < self.min_atr or a > self.max_atr:
            return None  # 無風 or 荒れすぎ → スキップ

        dev = price - e
        # 下に乖離しすぎ＆売られすぎ → 買い（中心回帰）
        if dev <= -self.dev_atr * a and r <= self.rsi_low:
            return Signal(
                side="BUY",
                price=price,
                lots=self.lots,
                take_profit=price + self.tp_atr * a,
                stop_loss=price - self.sl_atr * a,
                strategy="campaign/mean-reversion",
                reason=f"EMA{self.ema_period}から下方乖離 {dev:.3f}(≧{self.dev_atr}*ATR) & RSI {r:.1f}≦{self.rsi_low}",
                meta={"ema": e, "rsi": r, "atr": a},
            )
        # 上に乖離しすぎ＆買われすぎ → 売り
        if dev >= self.dev_atr * a and r >= self.rsi_high:
            return Signal(
                side="SELL",
                price=price,
                lots=self.lots,
                take_profit=price - self.tp_atr * a,
                stop_loss=price + self.sl_atr * a,
                strategy="campaign/mean-reversion",
                reason=f"EMA{self.ema_period}から上方乖離 {dev:.3f}(≧{self.dev_atr}*ATR) & RSI {r:.1f}≧{self.rsi_high}",
                meta={"ema": e, "rsi": r, "atr": a},
            )
        return None
