"""設定ローダ。JSON（純標準ライブラリ）。

config.json が無ければ config.example.json を読む。
"""

from __future__ import annotations

import json
import os

_DEFAULT_CANDIDATES = ["config.json", "config.example.json"]


def load_config(path: str | None = None) -> dict:
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    for cand in _DEFAULT_CANDIDATES:
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("config.json / config.example.json が見つかりません")
