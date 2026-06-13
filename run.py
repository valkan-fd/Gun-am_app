#!/usr/bin/env python3
"""エントリポイント。

使い方:
  python3 run.py                     # config.json(無ければ example) で起動
  python3 run.py --config my.json
  python3 run.py --demo              # 合成データで高速デモ（ネット不要・即終了）

モード/フィードは config 側で切替（mode: notify|paper|live, feed.mode: synthetic|replay|stooq）。
"""

from __future__ import annotations

import argparse

from src.config import load_config
from src.bot import Bot


def main() -> None:
    ap = argparse.ArgumentParser(description="みんなのFX 90lot/イベント シグナルBot")
    ap.add_argument("--config", default=None, help="設定ファイルパス")
    ap.add_argument("--demo", action="store_true", help="合成データで高速デモ（300tick）")
    args = ap.parse_args()

    cfg = load_config(args.config)

    if args.demo:
        cfg["mode"] = "paper"
        cfg.setdefault("feed", {})["mode"] = "synthetic"
        cfg["feed"]["seed"] = 42
        cfg["poll_seconds"] = 0
        cfg["bar_seconds"] = 1
        Bot(cfg).run(max_ticks=1500)
        return

    Bot(cfg).run()


if __name__ == "__main__":
    main()
