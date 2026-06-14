#!/usr/bin/env python3
"""【高勝率bot】エントリポイント — 低リスク・高ヒット率で 90lot を消化。

使い方:
  python3 run_winrate.py                      # config.winrate.json(無ければ example)
  python3 run_winrate.py --config my.json
  python3 run_winrate.py --demo               # 合成データで高速ペーパー検証
"""

from __future__ import annotations

import argparse

from src.config import load_config
from src.engine import Engine
from src.strategy_winrate import WinRateScalper

_CANDIDATES = ["config.winrate.json", "config.winrate.example.json"]


def main() -> None:
    ap = argparse.ArgumentParser(description="高勝率bot（90lot 低リスク消化）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    cfg = _load(args.config)
    if args.demo:
        cfg["mode"] = "paper"
        cfg.setdefault("feed", {}).update({"mode": "synthetic", "seed": 42})
        cfg["poll_seconds"] = 0
        cfg["bar_seconds"] = 1
        # デモは時刻に依存しないようセッション/レンジ制限を緩める
        cfg.setdefault("winrate", {}).update({"sessions_jst": None})
        Engine(cfg, WinRateScalper(cfg), label="高勝率").run(max_ticks=2000)
        return
    Engine(cfg, WinRateScalper(cfg), label="高勝率").run()


def _load(path):
    if path:
        return load_config(path)
    import os
    for c in _CANDIDATES:
        if os.path.exists(c):
            return load_config(c)
    return load_config("config.example.json")  # フォールバック


if __name__ == "__main__":
    main()
