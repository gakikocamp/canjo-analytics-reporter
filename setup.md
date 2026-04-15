# 週次レポート設定手順

## Step 1: Googleサービスアカウント作成（5分）

1. https://console.cloud.google.com/ を開く
2. プロジェクト選択 → 「新しいプロジェクト」→ 名前: `canjo-analytics`
3. 左メニュー「APIとサービス」→「ライブラリ」
4. 以下2つを有効化:
   - `Google Analytics Data API`
   - `Google Search Console API`
5. 「認証情報」→「サービスアカウントを作成」
   - 名前: `analytics-reporter`
   - ロール: なし（後で個別設定）
6. 作成したサービスアカウントをクリック → 「キー」タブ →「鍵を追加」→ JSON
   → ダウンロードした JSON ファイルを `service_account.json` として保存

## Step 2: 各GA4プロパティにサービスアカウントを追加（3分 × サイト数）

GA4管理画面 → プロパティ設定 → アクセス管理 → 「ユーザーを追加」
- メール: サービスアカウントのメールアドレス（`analytics-reporter@canjo-analytics.iam.gserviceaccount.com`のような形式）
- ロール: 「閲覧者」

## Step 3: 各GSCプロパティにサービスアカウントを追加（2分 × サイト数）

Search Console → 設定 → ユーザーと権限 → ユーザーを追加
- メール: 同じサービスアカウントのメール
- 権限: 「制限付き」でOK

## Step 4: LINE Notifyトークン取得（2分）

1. https://notify-bot.line.me/ja/ にアクセス
2. ログイン → 「マイページ」
3. 「トークンを発行する」→ トークン名: `週次レポート`
4. 通知先: 自分だけのチャット or グループ
5. 発行されたトークンをコピー

## Step 5: Claude Code ルーティン設定

### 方法A: Web UI (推奨)
1. https://claude.ai/code/scheduled を開く
2. 「New scheduled task」をクリック
3. 設定:
   - **名前**: Canjo 週次GA4+GSCレポート
   - **スケジュール**: Weekly / 月曜 / 09:00
   - **プロンプト**: (下記参照)
4. 環境変数に以下を設定:
   - `LINE_NOTIFY_TOKEN` = (取得したトークン)
   - `GA4_JDTLC` = (JDTLCのGA4プロパティID)
   - `GSC_CAMJYO` = https://www.camjyo.com/
   - `GSC_CRYSTAL` = https://crystalinsence.com/
   - `GSC_VANTRIP` = https://vantripjapan.jp/
   - `GSC_JDTLC` = (JDTLCのGSCプロパティURL)
   - `GOOGLE_APPLICATION_CREDENTIALS` = service_account.json の内容

### 方法B: CLIから設定
```
/schedule daily PR review at 9am Monday
```

## ルーティン用プロンプト（コピペ用）

```
以下の手順で週次アナリティクスレポートを生成してLINEに送信してください:

1. analytics-reporter/report.py を実行
2. 5サイト分のGA4・GSCデータを取得
3. 前週比較・上位クエリ・上位ページを含むレポートを生成
4. LINE Notifyでレポートを送信
5. 各サイトの主要な改善ポイントを3つずつ特定して追加で送信

対象サイト:
- キャンジョコーポレート (camjyo.com)
- CRYSTAL INCENSE (crystalinsence.com)
- VANTRIP JAPAN (vantripjapan.jp)
- JDTLC
- キャンプコンサルページ (camjyo.com/campconsul)

実行後、SEOで改善すべき最重要キーワードTOP5と
次週制作すべき記事タイトル案3本をレポートに追記してください。
```

## 確認済みGA4 プロパティID

| サイト | GA4 ID |
|--------|--------|
| camjyo.com + campconsul | G-BSWF4PM45S |
| crystalinsence.com | G-Q9YT04QEHX |
| vantripjapan.jp | G-RC4937NTHC |
| JDTLC | 要確認 |
