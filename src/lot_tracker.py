"""90lot キャンペーン進捗トラッカー & ペース配分。

1 lot = 1万通貨。キャンペーンは「新規」建玉の累計 lot を数える想定（決済は対象外が一般的）。
※ 実際の集計定義は必ず公式キャンペーン規約で確認すること。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


@dataclass
class LotState:
    target_lots: float = 90.0
    done_lots: float = 0.0
    deadline_iso: str = ""        # 例 "2026-08-12"
    started_iso: str = ""

    def remaining(self) -> float:
        return max(0.0, self.target_lots - self.done_lots)

    def days_left(self) -> int:
        if not self.deadline_iso:
            return 0
        d = date.fromisoformat(self.deadline_iso)
        today = datetime.now(JST).date()
        return max(0, (d - today).days)

    def lots_per_day(self) -> float:
        dl = self.days_left()
        return round(self.remaining() / dl, 2) if dl > 0 else self.remaining()


class LotTracker:
    def __init__(self, path: str, target_lots: float = 90.0, deadline_iso: str = "") -> None:
        self.path = path
        if os.path.exists(path):
            with open(path) as f:
                self.state = LotState(**json.load(f))
        else:
            self.state = LotState(
                target_lots=target_lots,
                deadline_iso=deadline_iso,
                started_iso=datetime.now(JST).date().isoformat(),
            )
            self.save()

    def add(self, lots: float) -> None:
        """新規建玉が約定したら呼ぶ。"""
        self.state.done_lots = round(self.state.done_lots + lots, 4)
        self.save()

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(asdict(self.state), f, ensure_ascii=False, indent=2)

    def status_line(self) -> str:
        s = self.state
        return (
            f"進捗 {s.done_lots:.1f}/{s.target_lots:.0f} lot "
            f"(残 {s.remaining():.1f}) / 残り {s.days_left()}日 / "
            f"推奨ペース {s.lots_per_day():.2f} lot/日"
        )
