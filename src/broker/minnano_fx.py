"""みんなのFX（トレイダーズ証券）API アダプタ —— 実発注用スタブ。

⚠⚠⚠ 重要 ⚠⚠⚠
  これは"枠"です。実エンドポイント/認証仕様は必ず公式の最新ドキュメントで確認し、
  TODO 箇所を埋めてから使ってください。未検証のまま本番資金で自動発注しないこと。

  - みんなのFX は 2023/10 に「外国為替FX」API を提供開始（Python/Node/Go サンプルあり）。
  - API キー作成から一定期間（公表値: 30日以内）の API 発注は手数料無料との情報あり。
    期間外/条件次第で手数料が発生し得るため、コストとキャンペーン消化の整合を要確認。
  - EA/API 経由の取引がキャンペーン集計対象か、必ず規約で確認（対象外の場合は手動で）。

  安全ガード:
    enabled=False（既定）の間は、place_order は実送信せず内容を返すだけ（dry-run）。
    実発注するには config で broker.minnano.enabled=true かつ API キー設定が必須。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request
from typing import Optional

from .base import BrokerAdapter
from ..signals import Signal


class MinnaNoFxBroker(BrokerAdapter):
    name = "minnano_fx"

    # TODO: 公式ドキュメントで実 URL を確認して差し替える
    BASE_URL = "https://api.example-minnanofx.invalid"  # ←要差し替え

    def __init__(self, cfg: dict) -> None:
        m = ((cfg.get("broker") or {}).get("minnano") or {})
        self.enabled = bool(m.get("enabled", False))
        self.api_key = m.get("api_key", "")
        self.api_secret = m.get("api_secret", "")
        self.symbol = m.get("symbol", "USD_JPY")
        self.dry_run = bool(m.get("dry_run", True))
        self._last_price: Optional[float] = None

    # --- 認証ヘッダ（HMAC 署名は一般的なパターン。実仕様に合わせて修正） ----------
    def _headers(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time() * 1000))
        # TODO: 公式の署名仕様（署名対象文字列の順序・エンコード）に合わせる
        message = ts + method + path + body
        sign = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": ts,
            "API-SIGN": sign,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: Optional[dict] = None):
        body = json.dumps(payload) if payload is not None else ""
        url = self.BASE_URL + path
        req = urllib.request.Request(
            url, data=body.encode() if body else None,
            headers=self._headers(method, path, body), method=method,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    # --- BrokerAdapter 実装 -----------------------------------------------
    def place_order(self, signal: Signal) -> Optional[str]:
        # 1lot=1万通貨。みんなのFXの数量単位（通貨数 or lot）は実仕様で確認
        order = {
            "symbol": self.symbol,
            "side": signal.side,            # "BUY" / "SELL" （実仕様の表記に合わせる）
            "size": int(signal.lots * 10000),
            "executionType": "MARKET",
            # OCO/IFD-OCO で TP/SL を同時送信できる。実フィールド名は要確認:
            "takeProfit": signal.take_profit,
            "stopLoss": signal.stop_loss,
        }
        if not self.enabled or self.dry_run:
            print(f"[minnano_fx][DRY-RUN] 実送信せず: {order}")
            return "dryrun"
        # TODO: 実 path に差し替え
        resp = self._request("POST", "/v1/order", order)
        return str(resp.get("orderId")) if isinstance(resp, dict) else None

    def current_price(self) -> Optional[float]:
        if not self.enabled:
            return self._last_price
        # TODO: 実 ticker path に差し替え
        try:
            resp = self._request("GET", f"/v1/ticker?symbol={self.symbol}")
            self._last_price = float(resp["last"])
        except Exception as e:
            print(f"[minnano_fx] ticker 取得失敗: {e}")
        return self._last_price
