"""価格フィード。

3 モードを用意:
  - SyntheticFeed : 乱数ウォーク。ネット不要。すぐ動作確認できる（既定）。
  - ReplayFeed    : CSV(timestamp,price) を再生。バックテスト用。
  - StooqLiveFeed : Stooq の無料 CSV から USD/JPY 等を取得（要ネット, 追加 pip 不要）。

いずれも next() で (epoch_seconds, price) を返す共通インターフェース。
本番のみんなのFXの約定価格とは異なるため、シグナル判定の補助データとして使う想定。
"""

from __future__ import annotations

import csv
import io
import random
import time
import urllib.request
from typing import Iterator, Optional, Tuple

Tick = Tuple[float, float]  # (epoch_seconds, price)


class SyntheticFeed:
    """幾何ブラウン運動風のダミー価格。動作確認・デモ用。"""

    def __init__(self, start: float = 157.50, vol: float = 0.03, seed: Optional[int] = None,
                 tick_seconds: float = 5.0) -> None:
        self.price = start
        self.vol = vol
        self._rng = random.Random(seed)
        # 仮想クロック。poll_seconds=0 の高速デモでも足が確定するよう tick 毎に時間を進める。
        self._vclock = time.time()
        self._tick_seconds = tick_seconds

    def next(self) -> Tick:
        # ドリフトわずか + ボラ。時々スパイク（イベント疑似）。
        shock = 0.0
        if self._rng.random() < 0.01:
            shock = self._rng.choice([-1, 1]) * self.vol * self._rng.uniform(8, 20)
        step = self._rng.gauss(0, self.vol) + shock
        self.price = max(0.01, self.price + step)
        self._vclock += self._tick_seconds
        return self._vclock, round(self.price, 3)


class ReplayFeed:
    """CSV(timestamp,price) を 1 行ずつ返す。timestamp は epoch でも ISO でも数値でも可。"""

    def __init__(self, path: str) -> None:
        self._rows: list[Tick] = []
        with open(path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 2:
                    continue
                ts_raw, price_raw = row[0], row[1]
                try:
                    ts = float(ts_raw)
                except ValueError:
                    ts = time.time()
                self._rows.append((ts, float(price_raw)))
        self._iter: Iterator[Tick] = iter(self._rows)

    def next(self) -> Optional[Tick]:
        return next(self._iter, None)


class StooqLiveFeed:
    """Stooq の無料スナップショット CSV から最新値を取得。

    symbol 例: 'usdjpy', 'eurjpy', 'gbpjpy'。
    レート制限・遅延あり。本番発注には必ずブローカー側レートを使うこと。
    """

    URL = "https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"

    def __init__(self, symbol: str = "usdjpy", timeout: float = 8.0) -> None:
        self.symbol = symbol.lower()
        self.timeout = timeout

    def next(self) -> Optional[Tick]:
        url = self.URL.format(sym=self.symbol)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
            reader = csv.DictReader(io.StringIO(text))
            row = next(reader, None)
            if not row:
                return None
            close = row.get("Close") or row.get("close")
            if close in (None, "", "N/D"):
                return None
            return time.time(), float(close)
        except Exception:
            return None


def build_feed(cfg: dict):
    mode = (cfg.get("feed", {}) or {}).get("mode", "synthetic")
    fcfg = cfg.get("feed", {}) or {}
    if mode == "synthetic":
        return SyntheticFeed(
            start=float(fcfg.get("start", 157.5)),
            vol=float(fcfg.get("vol", 0.03)),
            seed=fcfg.get("seed"),
        )
    if mode == "replay":
        return ReplayFeed(fcfg["path"])
    if mode == "stooq":
        return StooqLiveFeed(symbol=fcfg.get("symbol", "usdjpy"))
    raise ValueError(f"unknown feed mode: {mode}")
