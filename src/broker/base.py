"""ブローカー・アダプタの抽象基底。

シグナル → 実発注の境界。notify-only 運用なら発注は呼ばれない。
PaperBroker でシミュレーション、MinnaNoFxBroker で実発注（要 API 設定・既定で無効）。
"""

from __future__ import annotations

import abc
from typing import Optional

from ..signals import Signal


class BrokerAdapter(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def place_order(self, signal: Signal) -> Optional[str]:
        """新規注文を出す。約定/受付できたら注文IDを返す。失敗なら None。"""

    @abc.abstractmethod
    def current_price(self) -> Optional[float]:
        ...

    def close_all(self) -> None:
        """保有を全決済（任意実装）。"""
        return None
