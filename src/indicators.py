"""テクニカル指標（純標準ライブラリ実装）。

すべて「直近 N 本の終値リスト」等を受け取り、最新値を返すシンプルな関数群。
バックテストでもライブでも同じ関数を使う。
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, List, Optional, Sequence


def sma(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: Sequence[float], period: int) -> Optional[float]:
    """指数移動平均。先頭を SMA でシードして安定化させる。"""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    e = seed
    for v in values[period:]:
        e = v * k + e * (1.0 - k)
    return e


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    """Wilder の RSI。0-100。"""
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    # 最初の period 本で平均利得/損失を作る
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    # 以降を Wilder 平滑化
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr_from_closes(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """高値・安値が無い終値のみのフィードでも使える近似 ATR。

    隣接終値の絶対差（=擬似トゥルーレンジ）の平均。Tick/終値ベースの簡易ボラ指標。
    """
    if len(closes) < period + 1:
        return None
    diffs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    return sum(diffs[-period:]) / period


def bollinger(values: Sequence[float], period: int = 20, mult: float = 2.0):
    """(中央, 上限, 下限, 標準偏差) を返す。"""
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((v - mid) ** 2 for v in window) / period
    sd = math.sqrt(var)
    return mid, mid + mult * sd, mid - mult * sd, sd


def rolling_high_low(values: Sequence[float], period: int):
    if len(values) < period:
        return None
    window = values[-period:]
    return max(window), min(window)


class RollingWindow:
    """固定長の終値バッファ。"""

    def __init__(self, maxlen: int = 5000) -> None:
        self._buf: Deque[float] = deque(maxlen=maxlen)

    def push(self, value: float) -> None:
        self._buf.append(value)

    def values(self) -> List[float]:
        return list(self._buf)

    def __len__(self) -> int:
        return len(self._buf)
