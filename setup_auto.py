#!/usr/bin/env python3
"""
Canjo Analytics Reporter — セットアップ
GA4の数値IDを入力するだけで完了。OAuthは不要。
"""

import os, sys, json, subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SA_EMAIL   = "analytics-reporter@canjo-analytics-reporter.iam.gserviceaccount.com"
SA_JSON    = SCRIPT_DIR / "service_account.json"
ENV_FILE   = SCRIPT_DIR / ".env"
REPORT_PY  = SCRIPT_DIR / "report.py"

SITES = [
    ("camjyo",  "G-BSWF4PM45S", "camjyo.com + キャンプコンサル"),
    ("crystal", "G-Q9YT04QEHX", "crystalinsence.com"),
    ("vantrip", "G-RC4937NTHC", "vantripjapan.jp"),
    ("jdtlc",   "G-EN3734XZMP", "drive-japan-license.com"),
]

OLD_IDS = {
    "camjyo":  "BSWF4PM45S",
    "crystal": "Q9YT04QEHX",
    "vantrip": "RC4937NTHC",
    "jdtlc":   "EN3734XZMP",
}

GSC_URLS = {
    "camjyo":  "https://www.camjyo.com/",
    "crystal": "https://crystalinsence.com/",
    "vantrip": "https://vantripjapan.jp/",
    "jdtlc":   "https://drive-japan-license.com/",
}

def show_instructions():
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║  Step 1: GA4にサービスアカウントを追加（4プロパティ）         ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  1. https://analytics.google.com を開く                       ║
║  2. 左下「管理」→「プロパティのアクセス管理」                  ║
║  3. 右上「＋」→「ユーザーを追加」                             ║
║  4. メールアドレス:                                           ║
║     {SA_EMAIL}  ║
║  5. ロール:「閲覧者」→「追加」                                ║
║  6. ★ URLを見て数値IDをメモ                                  ║
║     例: analytics.google.com/analytics/web/#/p[数値ID]/...   ║
║     または「管理」>「プロパティ設定」>「プロパティID」         ║
║                                                               ║
║  上の操作を4つのプロパティで繰り返す:                         ║
║  ・G-BSWF4PM45S (camjyo.com)                                 ║
║  ・G-Q9YT04QEHX (crystalinsence.com)                         ║
║  ・G-RC4937NTHC (vantripjapan.jp)                            ║
║  ・G-EN3734XZMP (drive-japan-license.com)                    ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║  Step 2: GSCにも同じアドレスを追加（4プロパティ）             ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  https://search.google.com/search-console                     ║
║  各サイト → 設定 → ユーザーと権限 → ユーザーを追加           ║
║  メール: 上と同じ / 権限:「制限付き」                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
""")

def get_property_ids():
    print("[Step 3] GA4の数値プロパティIDを入力してください")
    print("  （GA4の「管理」>「プロパティ設定」>「プロパティID」の数字）\n")
    ids = {}
    for key, meas_id, label in SITES:
        while True:
            val = input(f"  {label} ({meas_id})\n  プロパティID（数字のみ）: ").strip()
            if val.isdigit():
                ids[key] = val
                break
            elif val == "":
                print("  スキップします")
                break
            else:
                print("  数字のみ入力してください")
    return ids

def update_report_py(ids):
    print("\n[Step 4] report.py を更新中...")
    content = REPORT_PY.read_text()
    updated = content
    for key, numeric_id in ids.items():
        old = f'"{OLD_IDS[key]}"'
        new = f'"{numeric_id}"'
        if old in updated:
            updated = updated.replace(old, new)
            print(f"  ✓ {key}: {OLD_IDS[key]} → {numeric_id}")
    if updated != content:
        REPORT_PY.write_text(updated)
        print("  保存完了")
    else:
        print("  変更なし（既に設定済みの可能性あり）")

def generate_env():
    print("\n[Step 5] 環境変数を設定中...")

    # 既存の.envからLINE tokenを読む
    existing_token = ""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("LINE_NOTIFY_TOKEN="):
                existing_token = line.split("=", 1)[1].strip()

    if existing_token:
        print(f"  LINE Notifyトークン: 設定済み（変更する場合は新しいトークンを入力）")
        line_token = input("  LINE_NOTIFY_TOKEN (変更なしはEnter): ").strip() or existing_token
    else:
        print("  LINE Notifyトークンを入力してください")
        print("  取得先: https://notify-bot.line.me/ja/ > マイページ > トークンを発行")
        line_token = input("  LINE_NOTIFY_TOKEN: ").strip()

    ENV_FILE.write_text(f"""# Canjo Analytics Reporter
GOOGLE_APPLICATION_CREDENTIALS={SA_JSON}
LINE_NOTIFY_TOKEN={line_token}
GSC_CAMJYO=https://www.camjyo.com/
GSC_CRYSTAL=https://crystalinsence.com/
GSC_VANTRIP=https://vantripjapan.jp/
GSC_JDTLC=https://drive-japan-license.com/
""")
    print("  ✓ .env 生成完了")

def test_connection(ids):
    print("\n[Step 6] 接続テスト中（LINE送信なし）...")

    if not ids:
        print("  プロパティIDが未入力のためスキップ")
        return

    # 最初の1プロパティだけテスト
    first_key = list(ids.keys())[0]
    first_id  = ids[first_key]

    test_code = f"""
import warnings, os
warnings.filterwarnings('ignore')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '{SA_JSON}'
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric
from datetime import date, timedelta

today = date.today()
end   = today - timedelta(days=1)
start = end - timedelta(days=6)

client = BetaAnalyticsDataClient()
req = RunReportRequest(
    property='properties/{first_id}',
    metrics=[Metric(name='sessions')],
    date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
)
resp = client.run_report(req)
total = sum(int(r.metric_values[0].value) for r in resp.rows)
print(f'✅ {first_key}: セッション数 {{total:,}} 件（{start} 〜 {end}）')
"""
    result = subprocess.run([sys.executable, "-c", test_code], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  {result.stdout.strip()}")
        print("\n  ✅ GA4接続テスト成功！")
    else:
        err = result.stderr
        if "PERMISSION_DENIED" in err:
            print(f"  ✗ 権限エラー: サービスアカウントがGA4に追加されているか確認してください")
            print(f"    SA: {SA_EMAIL}")
        elif "NOT_FOUND" in err:
            print(f"  ✗ プロパティID '{first_id}' が見つかりません。数値を確認してください")
        else:
            print(f"  ✗ エラー: {err[:300]}")

def test_gsc():
    print("\n[Step 7] GSC接続テスト中...")
    test_code = f"""
import warnings, os
warnings.filterwarnings('ignore')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '{SA_JSON}'
from google.oauth2 import service_account
from googleapiclient.discovery import build

scopes = ['https://www.googleapis.com/auth/webmasters.readonly']
creds = service_account.Credentials.from_service_account_file('{SA_JSON}', scopes=scopes)
service = build('searchconsole', 'v1', credentials=creds)

from datetime import date, timedelta
today = date.today()
end = str(today - timedelta(days=1))
start = str(today - timedelta(days=7))

results = []
for url in ['https://www.camjyo.com/', 'https://crystalinsence.com/', 'https://vantripjapan.jp/', 'https://drive-japan-license.com/']:
    try:
        body = {{'startDate': start, 'endDate': end, 'dimensions': ['query'], 'rowLimit': 1}}
        resp = service.searchanalytics().query(siteUrl=url, body=body).execute()
        results.append(f'✅ {{url}} — OK')
    except Exception as e:
        results.append(f'✗ {{url}} — {{str(e)[:60]}}')

for r in results:
    print(r)
"""
    result = subprocess.run([sys.executable, "-c", test_code], capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr[:500])

def main():
    print("=" * 60)
    print("  Canjo Analytics Reporter — セットアップ")
    print("=" * 60)

    # Step 1-2: 手順説明
    show_instructions()
    input("  GA4・GSCへの追加が完了したら Enter を押してください...")

    # Step 3: プロパティID入力
    ids = get_property_ids()

    # Step 4: report.py更新
    if ids:
        update_report_py(ids)

    # Step 5: .env生成
    generate_env()

    # Step 6: GA4接続テスト
    if ids:
        test_connection(ids)

    # Step 7: GSC接続テスト
    test_gsc()

    print("\n" + "=" * 60)
    print("✅ セットアップ完了！")
    print("=" * 60)
    print("週次実行: 毎週月曜日 9:00（macOS launchd登録済み）")
    print("手動テスト: python3 report.py")

if __name__ == "__main__":
    main()
