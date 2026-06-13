"""ペーパートレード（シミュレーション）ブローカー。

スプレッドコストを引いた擬似約定を行い、TP/SL をローカルで監視して損益を記録。
"寝てる間に勝手に本番発注"を避けつつ、戦略の挙動・消化ロットを検証できる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .base import BrokerAdapter
from ..signals import Signal


@dataclass
class Position:
    side: str
    entry: float
    lots: float
    tp: Optional[float]
    sl: Optional[float]
    strategy: str


@dataclass
class PaperBroker(BrokerAdapter):
    spread_yen: float = 0.002      # 0.2銭（USD/JPY 想定）
    yen_per_pip_per_lot: float = 100.0  # 1lot(1万通貨)・1銭(0.01円)あたり 100円
    name: str = "paper"
    _price: float = 0.0
    positions: List[Position] = field(default_factory=list)
    realized_pnl_yen: float = 0.0
    new_lots_total: float = 0.0    # キャンペーン対象（新規）累計

    def update_price(self, price: float) -> List[str]:
        """価格更新。TP/SL に当たったポジションを決済し、ログ文字列を返す。"""
        self._price = price
        logs: List[str] = []
        still: List[Position] = []
        for p in self.positions:
            hit = None
            if p.side == "BUY":
                if p.sl is not None and price <= p.sl:
                    hit = ("SL", p.sl)
                elif p.tp is not None and price >= p.tp:
                    hit = ("TP", p.tp)
            else:  # SELL
                if p.sl is not None and price >= p.sl:
                    hit = ("SL", p.sl)
                elif p.tp is not None and price <= p.tp:
                    hit = ("TP", p.tp)
            if hit:
                kind, exit_px = hit
                pnl = self._pnl_yen(p, exit_px)
                self.realized_pnl_yen += pnl
                logs.append(
                    f"[paper] {kind} 決済 {p.side} {p.lots}lot {p.entry:.3f}->{exit_px:.3f} "
                    f"損益 {pnl:+.0f}円 (累計 {self.realized_pnl_yen:+.0f}円)"
                )
            else:
                still.append(p)
        self.positions = still
        return logs

    def _pnl_yen(self, p: Position, exit_px: float) -> float:
        diff = (exit_px - p.entry) if p.side == "BUY" else (p.entry - exit_px)
        pips = diff / 0.01  # 銭
        gross = pips * self.yen_per_pip_per_lot * p.lots
        cost = (self.spread_yen / 0.01) * self.yen_per_pip_per_lot * p.lots  # 片道スプレッド
        return gross - cost

    def place_order(self, signal: Signal) -> Optional[str]:
        entry = (signal.price + self.spread_yen) if signal.side == "BUY" else (signal.price - self.spread_yen)
        self.positions.append(
            Position(signal.side, entry, signal.lots, signal.take_profit, signal.stop_loss, signal.strategy)
        )
        self.new_lots_total += signal.lots
        return f"paper-{len(self.positions)}-{int(entry*1000)}"

    def current_price(self) -> Optional[float]:
        return self._price or None

    def close_all(self) -> None:
        for p in self.positions:
            self.realized_pnl_yen += self._pnl_yen(p, self._price)
        self.positions.clear()
