"""イベントドリブン（高ボラで一気に）& 為替介入シナリオ戦略。

対象イベント（JST）:
  - 日銀 金融政策決定会合 結果 + 総裁会見: 6/16（昼〜15:30 会見）
  - FOMC 結果 + パウエル会見       : 6/18 03:00 / 03:30（=米 6/17 14:00 ET）
  - MOF/日銀の円買い介入（時期不定・USD/JPY 急落リスク）

■ 設計思想
  高ボラ局面は"勝率"より"損小利大 + リスク限定"が命。ナケットで突っ込まない。
  2 つのモードを提供:

  (A) ブレイクアウト（イベント直後の方向に乗る）
      イベント直前の一定時間レンジ(high/low)を基準に、上抜け→買い / 下抜け→売り。
      損切りはレンジ反対側 or ATR ベース。指標発表の初動スパイクは取りに行かず、
      "ブレイク確定後"に追随する設計（ヒゲ・スリッページ・スプレッド拡大対策）。

  (B) 介入フェード/順張り（円買い介入シナリオ）
      USD/JPY が短時間で急騰し過熱（intervention_watch_level 接近 or 急騰速度超過）→
      介入による急落に備えた売り目線シグナル（リスク限定・小ロット）。
      逆に既に急落が始まった場合は順張り売り追随も選択肢として通知。

⚠ 重要な注意:
  - 介入のタイミング・有無は誰にも予測不能。スリッページ/窓開け/スプレッド拡大が激烈。
  - イベント時は必ず小ロット & 逆指値必須。レバレッジを上げて"一気に"は破産リスク直結。
  - 本モジュールは「シグナル/通知」であり、自動発注は既定で無効（README 参照）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from .indicators import atr_from_closes, rolling_high_low
from .signals import Signal

JST = timezone(timedelta(hours=9))


@dataclass
class EventWindow:
    name: str
    start: datetime   # JST。この時刻から「直前レンジ計測 → ブレイク監視」モードに入る
    end: datetime     # この時刻でイベントモード終了


def default_event_windows(year: int = 2026) -> List[EventWindow]:
    """2026/6 の主要イベント窓（JST）。日付は確定情報に基づく。"""
    def jst(m, d, hh, mm=0):
        return datetime(year, m, d, hh, mm, tzinfo=JST)

    return [
        # 日銀: 6/16 結果は昼頃、会見 15:30。11:00〜18:00 を監視窓に。
        EventWindow("BOJ 日銀(結果+会見)", jst(6, 16, 11, 0), jst(6, 16, 18, 0)),
        # FOMC: 6/18 03:00 結果 / 03:30 会見（米 6/17 14:00ET）。02:30〜05:30 を監視窓に。
        EventWindow("FOMC(結果+会見)", jst(6, 18, 2, 30), jst(6, 18, 5, 30)),
    ]


class EventStrategy:
    name = "volatility"

    def __init__(self, cfg: dict) -> None:
        e = (cfg.get("event") or {})
        self.range_lookback = int(e.get("range_lookback", 60))  # ブレイク基準レンジの本数
        self.atr_period = int(e.get("atr_period", 14))
        self.breakout_buffer_atr = float(e.get("breakout_buffer_atr", 0.25))  # ダマシ除け
        self.lots = float(e.get("lots_per_trade", 1.0))
        self.tp_atr = float(e.get("tp_atr", 2.5))
        self.sl_atr = float(e.get("sl_atr", 1.2))
        self.trail_atr = float(e.get("trail_atr", 1.5))  # 含み益方向にSL追従し利を伸ばす
        self.always_watch_intervention = bool(e.get("always_watch_intervention", True))
        # 介入監視
        self.intervention_level = float(e.get("intervention_watch_level", 160.0))
        self.spike_lookback = int(e.get("spike_lookback", 30))
        self.spike_threshold = float(e.get("spike_threshold_yen", 1.0))  # この本数で X円急騰=過熱
        self.windows = default_event_windows(int(e.get("year", 2026)))
        self._last_break: Optional[str] = None  # 同方向ブレイクの連投抑制

    # --- 窓判定 -----------------------------------------------------------
    def active_window(self, now: Optional[datetime] = None) -> Optional[EventWindow]:
        now = now or datetime.now(JST)
        for w in self.windows:
            if w.start <= now <= w.end:
                return w
        return None

    def next_window(self, now: Optional[datetime] = None) -> Optional[EventWindow]:
        now = now or datetime.now(JST)
        future = [w for w in self.windows if w.start > now]
        return min(future, key=lambda w: w.start) if future else None

    # --- 介入シナリオ -----------------------------------------------------
    def intervention_signal(self, closes: List[float]) -> Optional[Signal]:
        if len(closes) < self.spike_lookback + 1:
            return None
        price = closes[-1]
        past = closes[-self.spike_lookback - 1]
        move = price - past
        a = atr_from_closes(closes, self.atr_period) or 0.0
        # 介入警戒水準への接近 + 直近の急騰 → 円買い介入に備えた売り目線
        approaching = price >= self.intervention_level - max(0.5, 3 * a)
        spiking_up = move >= self.spike_threshold
        if approaching and spiking_up:
            return Signal(
                side="SELL",
                price=price,
                lots=self.lots,
                take_profit=price - self.tp_atr * max(a, 0.05),
                stop_loss=price + self.sl_atr * max(a, 0.05),
                strategy="event/intervention-fade",
                urgency="high",
                reason=(
                    f"USD/JPY {price:.3f} が介入警戒水準 {self.intervention_level} へ接近 & "
                    f"直近{self.spike_lookback}本で +{move:.2f}円 の急騰。"
                    f"円買い介入による急落リスク → 売り目線（⚠小ロット/逆指値必須）"
                ),
                meta={"move": move, "atr": a},
            )
        return None

    # --- ブレイクアウト ---------------------------------------------------
    def breakout_signal(self, closes: List[float]) -> Optional[Signal]:
        hl = rolling_high_low(closes[:-1], self.range_lookback)  # 直近(現足除く)レンジ
        a = atr_from_closes(closes, self.atr_period)
        if hl is None or a is None or a <= 0:
            return None
        hi, lo = hl
        price = closes[-1]
        buf = self.breakout_buffer_atr * a
        if price > hi + buf and self._last_break != "UP":
            self._last_break = "UP"
            return Signal(
                side="BUY", price=price, lots=self.lots,
                take_profit=price + self.tp_atr * a,
                stop_loss=min(lo, price - self.sl_atr * a),
                trail_distance=self.trail_atr * a,
                strategy="event/breakout",
                urgency="high",
                reason=f"直近{self.range_lookback}本レンジ上限 {hi:.3f} を上抜け（buffer {buf:.3f}）。順張り買い・トレーリングで利を伸ばす",
                meta={"range_high": hi, "range_low": lo, "atr": a},
            )
        if price < lo - buf and self._last_break != "DOWN":
            self._last_break = "DOWN"
            return Signal(
                side="SELL", price=price, lots=self.lots,
                take_profit=price - self.tp_atr * a,
                stop_loss=max(hi, price + self.sl_atr * a),
                trail_distance=self.trail_atr * a,
                strategy="event/breakout",
                urgency="high",
                reason=f"直近{self.range_lookback}本レンジ下限 {lo:.3f} を下抜け（buffer {buf:.3f}）。順張り売り・トレーリングで利を伸ばす",
                meta={"range_high": hi, "range_low": lo, "atr": a},
            )
        return None

    def evaluate(self, closes: List[float], now: Optional[datetime] = None) -> Optional[Signal]:
        # 介入シグナルは窓に関係なく常時監視（介入は予告なし）
        if self.always_watch_intervention:
            iv = self.intervention_signal(closes)
            if iv is not None:
                return iv
        if self.active_window(now) is not None:
            return self.breakout_signal(closes)
        return None
