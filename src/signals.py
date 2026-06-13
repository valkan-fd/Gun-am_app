"""シグナル/注文意図の共通データ構造。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    side: str                 # "BUY" or "SELL"
    reason: str               # 人間向けの根拠
    price: float              # 参考シグナル価格
    lots: float = 1.0         # 1 lot = 1万通貨
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    strategy: str = ""
    urgency: str = "normal"   # "normal" | "high"
    meta: dict = field(default_factory=dict)

    def summary(self) -> str:
        tp = f"{self.take_profit:.3f}" if self.take_profit is not None else "-"
        sl = f"{self.stop_loss:.3f}" if self.stop_loss is not None else "-"
        return (
            f"{self.side} {self.lots}lot @ {self.price:.3f}  "
            f"(TP {tp} / SL {sl})\n戦略: {self.strategy}\n根拠: {self.reason}"
        )
