"""【高勝率bot】低リスク・高ヒット率の平均回帰スキャルプ（90lot 消化主眼）。

CampaignScalper を土台に、勝率を底上げするフィルタを追加:
  1) セッション・フィルタ : 流動性が高くスプレッドが安定する時間帯(JST)だけ稼働
  2) レンジ・フィルタ     : 長期EMAの傾きが緩い=レンジ相場のときだけ（平均回帰は
                            トレンド相場で負けやすいので、強トレンド時は見送る）
  3) クールダウン         : シグナル連投を抑え、ダマシの連敗を避ける
  4) 浅いTP/やや広いSL    : 小さく何度も利確→高い勝率（その分1回の利は小さい）

⚠ 思想: これは「勝率を上げて 90lot を低リスクに消化」する設計。
   1トレードの期待値は薄い（スプレッド分はコスト）。大勝ちは高ボラbotの担当。
"""

from __future__ import annotations

from typing import List, Optional

from .indicators import ema
from .signals import Signal
from .strategy_campaign import CampaignScalper


class WinRateScalper(CampaignScalper):
    name = "winrate"

    def __init__(self, cfg: dict) -> None:
        super().__init__(cfg)
        w = (cfg.get("winrate") or {})
        # 稼働時間(JST)。[[16,26]] = 16:00〜翌2:00。複数指定可。Noneで24h。
        self.sessions = w.get("sessions_jst", [[16, 26]])
        # レンジ判定: 長期EMAの直近 slope_bars 本の変化が slope_max_atr*ATR 以下なら"レンジ"
        self.trend_ema = int(w.get("trend_ema", 100))
        self.slope_bars = int(w.get("slope_bars", 20))
        self.slope_max_atr = float(w.get("slope_max_atr", 1.5))
        self.cooldown_bars = int(w.get("cooldown_bars", 5))
        self._cooldown = 0

    def _in_session(self, now) -> bool:
        if now is None or not self.sessions:
            return True
        h = now.hour
        for start, end in self.sessions:
            s, e = start % 24, end
            if e <= 24:
                if s <= h < e:
                    return True
            else:  # 日跨ぎ（例 16〜26 = 16:00〜翌2:00）
                if h >= s or h < (e - 24):
                    return True
        return False

    def _is_range(self, closes: List[float]) -> bool:
        if len(closes) < self.trend_ema + self.slope_bars + 2:
            return True  # データ不足時はブロックしない
        e_now = ema(closes, self.trend_ema)
        e_prev = ema(closes[:-self.slope_bars], self.trend_ema)
        if e_now is None or e_prev is None:
            return True
        from .indicators import atr_from_closes
        a = atr_from_closes(closes, self.atr_period) or 0.0
        if a <= 0:
            return True
        return abs(e_now - e_prev) <= self.slope_max_atr * a

    def evaluate(self, closes: List[float], now=None) -> Optional[Signal]:
        if self._cooldown > 0:
            self._cooldown -= 1
            return None
        if not self._in_session(now):
            return None
        if not self._is_range(closes):
            return None  # 強トレンド中は平均回帰を見送る（勝率優先）
        sig = super().evaluate(closes, now)
        if sig is not None:
            self._cooldown = self.cooldown_bars
            sig.strategy = "winrate/range-mean-reversion"
        return sig
