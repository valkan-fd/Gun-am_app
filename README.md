# Gun-am_app — みんなのFX 90lot / イベント シグナルBot

みんなのFX（トレイダーズ証券）の **30万円入金 × 90lot キャンペーン消化**を低リスクで進めつつ、
**6/16 日銀・6/18 FOMC・為替介入**などの高ボラ局面を狙う **シグナル通知 / ペーパー / 実発注** bot。

> **まず読む → [docs/strategy.md](docs/strategy.md)（戦略全文）** と **[docs/event-calendar.md](docs/event-calendar.md)**
> 純標準ライブラリのみ。`pip install` 不要。Python 3.9+。

---

## ⚠ 最重要（先に結論）

1. **本当の勝ち筋は"相場を当てる"ことではなく、"90lot を最小コストで消化してキャッシュバックを確定"させること。** 報酬は取引完了で確定するので期待値はここにある。「最高勝率で当て続けるbot」は誰にも作れない（できると言う人は嘘）。
2. あなたのメモの**日銀は1日ズレ**：正しくは **6/16（会見15:30 JST）**。FOMC は **6/18 03:00 JST** でOK。
3. **寝ている間の自動実発注はしない設計**。既定は **通知のみ(notify)**。`paper` で検証 → 規約とAPI仕様を確認 → 小ロットで `live`、の順で。
4. みんなのFX は**公式APIあり**だが、**API/EA取引がキャンペーン集計対象か必ず規約確認**。対象外なら手動で消化。

---

## クイックスタート

```bash
# 1) 即デモ（合成データでペーパートレード。ネット不要・すぐ終わる）
python3 run.py --demo

# 2) 設定を作る
cp config.example.json config.json    # 中身を編集（通知先・期限など）

# 3) 通知モードで起動（発注しない・最も安全）
python3 run.py

# テスト
python3 -m unittest discover -s tests -v
```

## 運用モード（`config.json` の `mode`）

| mode | 動作 | 用途 |
|---|---|---|
| `notify` | シグナルを通知のみ（**既定**） | まず質と頻度を観察 |
| `paper` | ペーパー約定・損益/消化lotをシミュレート | 検証 |
| `live` | みんなのFX へ実発注 | `broker.minnano.enabled=true` & `dry_run=false` が必須 |

## データフィード（`config.feed.mode`）
- `synthetic` … 乱数（ネット不要・既定）
- `replay` … CSV(`timestamp,price`) を再生（バックテスト）
- `stooq` … 無料スナップショットでライブ近似（遅延あり。**発注はブローカー価格で**）

## 通知先
コンソールは常時。任意で **Discord / Slack / Telegram / 汎用Webhook**（`config.notify`）。
※ LINE Notify は 2025/3 終了のため非対応。**Discord か Telegram 推奨**。

---

## 構成

```
run.py                     エントリポイント（--demo あり）
config.example.json        設定サンプル
src/
  bot.py                   メインループ（tick→足→指標→戦略→通知/約定）
  indicators.py            EMA / RSI / ATR / Bollinger / レンジ
  strategy_campaign.py     90lot 低リスク消化（平均回帰スキャルプ）
  strategy_event.py        イベント・ブレイク & 介入フェード（6/16,6/18窓）
  lot_tracker.py           90lot 進捗 & 残日数からの推奨ペース
  notifier.py              Discord/Slack/Telegram/Webhook 通知
  data_feed.py             synthetic / replay / stooq
  signals.py               シグナル共通データ構造
  broker/
    base.py                抽象アダプタ
    paper.py               ペーパートレード（スプレッド込み損益）
    minnano_fx.py          みんなのFX実発注スタブ（要TODO実装・既定で発注無効）
docs/
  strategy.md              戦略全文（必読）
  event-calendar.md        6月イベントの正確な日時(JST)
tests/                     unittest
```

## 実発注を有効化する前に（`src/broker/minnano_fx.py`）
1. 公式APIドキュメントで **BASE_URL / エンドポイント / 署名仕様 / 数量単位** を確認し TODO を埋める。
2. `config.broker.minnano`：`enabled=true`, `dry_run=false`, `api_key`/`api_secret` を設定。
3. **必ず最小ロットで短時間テスト**してから本運用。

## 免責
投資勧誘ではありません。FX はレバレッジにより**入金額を超える損失**が生じ得ます。
スプレッド・証拠金率・キャンペーン条件・会合日程は変動します。**必ず公式一次情報で確認**を。最終判断は自己責任。
