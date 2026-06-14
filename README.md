# Gun-am_app — みんなのFX 90lot / イベント シグナルBot（2本立て）

みんなのFX（トレイダーズ証券）向けの**2つの独立したbot**。共通エンジン上で別々に動かせる。

| bot | 目的 | 起動 | 戦略 | 性格 |
|---|---|---|---|---|
| 🎯 **高勝率bot** | 30万円×**90lot を低リスクに消化** | `python3 run_winrate.py` | セッション/レンジ/クールダウン付き平均回帰スキャルプ | 高ヒット率・薄利・低ドローダウン |
| ⚡ **高ボラbot** | **6/16日銀・6/18FOMC・介入で一気に** | `python3 run_volatility.py` | ブレイク順張り＋トレーリング＋介入フェード | 低勝率・損小利大・高リスク |

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
# --- 高勝率bot（90lot 低リスク消化）---
python3 run_winrate.py --demo                       # 合成データで即ペーパー検証
cp config.winrate.example.json config.winrate.json  # 設定（通知先・期限など）を編集
python3 run_winrate.py                               # 通知モードで起動（発注しない）

# --- 高ボラbot（イベント/介入で一気に）---
python3 run_volatility.py --demo                     # 介入スパイク込みの検証
cp config.volatility.example.json config.volatility.json
python3 run_volatility.py

# 2本同時に動かしてもOK（lot_state / config は別ファイル）
# テスト
python3 -m unittest discover -s tests -v
```

> 2つは**完全に別プロセス・別設定・別ロット記録**。役割が違うので資金も分けて運用する
> （目安：高勝率に8〜9割／高ボラに1〜2割）。詳細は [docs/strategy.md](docs/strategy.md)。

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
run_winrate.py             🎯 高勝率bot エントリポイント（--demo あり）
run_volatility.py          ⚡ 高ボラbot エントリポイント（--demo あり）
config.winrate.example.json    高勝率bot 設定サンプル
config.volatility.example.json 高ボラbot 設定サンプル
config.example.json        共通フォールバック設定
src/
  engine.py                共通エンジン（tick→足→戦略→通知/約定・勝率集計）
  strategy_winrate.py      🎯 高勝率: セッション/レンジ/クールダウン付き平均回帰
  strategy_campaign.py     └ その土台（平均回帰スキャルプ）
  strategy_event.py        ⚡ 高ボラ: ブレイク＋トレーリング＋介入フェード（6/16,6/18窓）
  indicators.py            EMA / RSI / ATR / Bollinger / レンジ
  lot_tracker.py           90lot 進捗 & 残日数からの推奨ペース
  notifier.py              Discord/Slack/Telegram/Webhook 通知
  data_feed.py             synthetic / replay / stooq
  signals.py               シグナル共通データ構造（TP/SL/トレーリング）
  broker/
    base.py                抽象アダプタ
    paper.py               ペーパートレード（スプレッド/トレーリング/勝率集計）
    minnano_fx.py          みんなのFX実発注スタブ（要TODO実装・既定で発注無効）
docs/
  strategy.md              戦略全文（必読）
  event-calendar.md        6月イベントの正確な日時(JST)
tests/                     unittest（指標・両bot）
```

## 実発注を有効化する前に（`src/broker/minnano_fx.py`）
1. 公式APIドキュメントで **BASE_URL / エンドポイント / 署名仕様 / 数量単位** を確認し TODO を埋める。
2. `config.broker.minnano`：`enabled=true`, `dry_run=false`, `api_key`/`api_secret` を設定。
3. **必ず最小ロットで短時間テスト**してから本運用。

## 免責
投資勧誘ではありません。FX はレバレッジにより**入金額を超える損失**が生じ得ます。
スプレッド・証拠金率・キャンペーン条件・会合日程は変動します。**必ず公式一次情報で確認**を。最終判断は自己責任。
