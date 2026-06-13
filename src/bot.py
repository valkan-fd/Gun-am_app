"""メインループ: フィード → 指標 → 戦略 → 通知 / (ペーパー約定) → ロット進捗。

運用モード（config: mode）:
  - "notify"  : シグナル通知のみ（既定・最も安全）。寝てる間に発注しない。
  - "paper"   : ペーパートレードで損益・消化ロットをシミュレーション。
  - "live"    : みんなのFX へ実発注（broker.minnano.enabled=true & dry_run=false が必須）。

時間足: tick を集約して bar_seconds 毎に1本の終値を確定し、確定足で判定する
（チャタリング防止）。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from .indicators import RollingWindow
from .signals import Signal
from .notifier import Notifier
from .strategy_campaign import CampaignScalper
from .strategy_event import EventStrategy
from .lot_tracker import LotTracker
from .data_feed import build_feed
from .broker.paper import PaperBroker

JST = timezone(timedelta(hours=9))


class Bot:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.mode = cfg.get("mode", "notify")
        self.bar_seconds = int(cfg.get("bar_seconds", 60))
        self.poll_seconds = float(cfg.get("poll_seconds", 1.0))
        self.max_bars = int(cfg.get("max_bars", 3000))

        self.feed = build_feed(cfg)
        self.notifier = Notifier(cfg)
        self.campaign = CampaignScalper(cfg)
        self.event = EventStrategy(cfg)
        self.window = RollingWindow(self.max_bars)

        lt = cfg.get("lot_tracker", {}) or {}
        self.tracker = LotTracker(
            path=lt.get("path", "lot_state.json"),
            target_lots=float(lt.get("target_lots", 90)),
            deadline_iso=lt.get("deadline", ""),
        )

        self.broker: Optional[PaperBroker] = None
        if self.mode == "paper":
            b = (cfg.get("broker") or {}).get("paper", {}) or {}
            self.broker = PaperBroker(
                spread_yen=float(b.get("spread_yen", 0.002)),
            )

        self._bar_open_ts: Optional[float] = None
        self._bar_last_price: Optional[float] = None
        self._last_signal_key: Optional[str] = None
        self._signals_today = 0
        self.max_signals_per_window = int(cfg.get("max_signals_per_window", 30))

    # --- 足の集約 ---------------------------------------------------------
    def _on_tick(self, ts: float, price: float) -> Optional[float]:
        """tick を受け、bar が確定したら確定足の終値を返す。"""
        if self.broker is not None:
            for log in self.broker.update_price(price):
                print(log)
        if self._bar_open_ts is None:
            self._bar_open_ts = ts
        self._bar_last_price = price
        if ts - self._bar_open_ts >= self.bar_seconds:
            close = self._bar_last_price
            self._bar_open_ts = ts
            return close
        return None

    # --- 1足確定時の処理 --------------------------------------------------
    def _on_bar_close(self, close: float) -> None:
        self.window.push(close)
        closes = self.window.values()
        now = datetime.now(JST)

        # 1) イベント/介入を優先評価
        sig = self.event.evaluate(closes, now)
        # 2) イベント窓外なら通常のキャンペーン消化を評価
        if sig is None and self.event.active_window(now) is None:
            sig = self.campaign.evaluate(closes)

        if sig is None:
            return

        key = f"{sig.strategy}:{sig.side}:{round(sig.price,2)}"
        if key == self._last_signal_key:
            return  # 直近と同一シグナルは抑制
        self._last_signal_key = key

        self._handle_signal(sig)

    def _handle_signal(self, sig: Signal) -> None:
        title = "🔔 シグナル" + ("（高優先・イベント/介入）" if sig.urgency == "high" else "")
        body = sig.summary() + "\n" + self.tracker.status_line()
        self.notifier.send(title, body)

        if self.mode == "paper" and self.broker is not None:
            oid = self.broker.place_order(sig)
            self.tracker.add(sig.lots)
            print(f"[paper] order={oid} 新規{sig.lots}lot 消化  累計新規 {self.broker.new_lots_total:.1f}lot")
        elif self.mode == "live":
            self._live_order(sig)
        # notify モードは通知のみ（発注しない）

    def _live_order(self, sig: Signal) -> None:
        from .broker.minnano_fx import MinnaNoFxBroker
        broker = MinnaNoFxBroker(self.cfg)
        oid = broker.place_order(sig)
        if oid and oid != "dryrun":
            self.tracker.add(sig.lots)
        self.notifier.send("✅ 実発注", f"order_id={oid}\n{sig.summary()}")

    # --- ループ -----------------------------------------------------------
    def run(self, max_ticks: Optional[int] = None) -> None:
        self.notifier.send(
            "🚀 Bot 起動",
            f"mode={self.mode} / feed={self.cfg.get('feed',{}).get('mode')}\n{self.tracker.status_line()}",
        )
        ticks = 0
        try:
            while True:
                tick = self.feed.next()
                if tick is None:
                    break  # replay 終了
                ts, price = tick
                close = self._on_tick(ts, price)
                if close is not None:
                    self._on_bar_close(close)
                ticks += 1
                if max_ticks is not None and ticks >= max_ticks:
                    break
                if self.poll_seconds > 0:
                    time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            print("\n停止します。")
        finally:
            if self.broker is not None:
                pnl = self.broker.realized_pnl_yen
                print(f"\n[paper] 確定損益 {pnl:+.0f}円 / 新規消化 {self.broker.new_lots_total:.1f}lot")
                print(self.tracker.status_line())
