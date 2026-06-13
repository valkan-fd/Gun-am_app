"""通知。コンソールは常時。任意で Discord / Telegram / Slack / 汎用 Webhook。

すべて標準ライブラリ(urllib)で送信。requests 等は不要。
※ LINE Notify は 2025/3 で終了したため非対応。Discord か Telegram を推奨。
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

JST = timezone(timedelta(hours=9))


def _now_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def _post_json(url: str, payload: dict, timeout: float = 8.0) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as e:  # 通知失敗で bot を止めない
        print(f"[notifier] 送信失敗: {e}")
        return False


class Notifier:
    def __init__(self, cfg: dict) -> None:
        n = cfg.get("notify", {}) or {}
        self.console: bool = bool(n.get("console", True))
        self.discord_webhook: Optional[str] = n.get("discord_webhook") or None
        self.slack_webhook: Optional[str] = n.get("slack_webhook") or None
        self.telegram_token: Optional[str] = n.get("telegram_token") or None
        self.telegram_chat_id: Optional[str] = n.get("telegram_chat_id") or None
        self.generic_webhook: Optional[str] = n.get("generic_webhook") or None

    def send(self, title: str, body: str) -> None:
        msg = f"【{title}】 {_now_jst()}\n{body}"
        if self.console:
            print("\n" + "=" * 60 + f"\n{msg}\n" + "=" * 60)
        if self.discord_webhook:
            _post_json(self.discord_webhook, {"content": msg[:1900]})
        if self.slack_webhook:
            _post_json(self.slack_webhook, {"text": msg})
        if self.generic_webhook:
            _post_json(self.generic_webhook, {"title": title, "body": body, "ts": _now_jst()})
        if self.telegram_token and self.telegram_chat_id:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            _post_json(url, {"chat_id": self.telegram_chat_id, "text": msg})
