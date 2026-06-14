#!/usr/bin/env python3
"""【高ボラbot】エントリポイント — 6/16日銀・6/18FOMC・為替介入で"一気に"狙う。

ブレイクアウト順張り＋トレーリングで利を伸ばし、介入急落シナリオも常時監視。
⚠ 低勝率・高リスク。必ず小ロット＋逆指値。寝てる間の自動実発注は非推奨（既定 notify）。

使い方:
  python3 run_volatility.py                   # config.volatility.json(無ければ example)
  python3 run_volatility.py --config my.json
  python3 run_volatility.py --demo            # 介入スパイクを含む合成データで検証
"""

from __future__ import annotations

import argparse

from src.config import load_config
from src.engine import Engine
from src.strategy_event import EventStrategy

_CANDIDATES = ["config.volatility.json", "config.volatility.example.json"]


def main() -> None:
    ap = argparse.ArgumentParser(description="高ボラbot（イベント/介入で一気に）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    cfg = _load(args.config)
    if args.demo:
        cfg["mode"] = "paper"
        # 介入監視が発火するよう高値圏＆高ボラの合成データに
        cfg.setdefault("feed", {}).update({"mode": "synthetic", "seed": 7, "start": 158.5, "vol": 0.06})
        cfg["poll_seconds"] = 0
        cfg["bar_seconds"] = 1
        Engine(cfg, EventStrategy(cfg), label="高ボラ").run(max_ticks=2000)
        return
    Engine(cfg, EventStrategy(cfg), label="高ボラ").run()


def _load(path):
    if path:
        return load_config(path)
    import os
    for c in _CANDIDATES:
        if os.path.exists(c):
            return load_config(c)
    return load_config("config.example.json")


if __name__ == "__main__":
    main()
