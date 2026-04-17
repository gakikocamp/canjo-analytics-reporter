#!/usr/bin/env python3
"""
Canjo Analytics Reporter — 自動セットアップスクリプト
このスクリプトを1回だけ実行すると:
  1. GA4の数値プロパティIDを自動取得
  2. サービスアカウントを各GA4プロパティに自動追加
  3. GSCプロパティへのアクセス確認
  4. report.py の property IDを修正
  5. 環境変数ファイルを生成
"""

import os
import sys
import json
import subprocess

SA_EMAIL = "analytics-reporter@canjo-analytics-reporter.iam.gserviceaccount.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SA_JSON_PATH = os.path.join(SCRIPT_DIR, "service_account.json")

MEASUREMENT_IDS = {
    "camjyo":  "G-BSWF4PM45S",
    "crystal": "G-Q9YT04QEHX",
    "vantrip": "G-RC4937NTHC",
    "jdtlc":   "G-EN3734XZMP",
}

GSC_URLS = {
    "camjyo":  "https://www.camjyo.com/",
    "crystal": "https://crystalinsence.com/",
    "vantrip": "https://vantripjapan.jp/",
    "jdtlc":   "https://drive-japan-license.com/",
}

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return None
    return result.stdout.strip()

def step1_auth():
    """Application Default Credentials でログイン（analytics スコープ付き）"""
    print("\n[Step 1] Google認証 (ブラウザが開きます...)")
    os.system(
        'export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH" && '
        'gcloud auth application-default login '
        '--scopes='
        '"https://www.googleapis.com/auth/analytics.readonly,'
        'https://www.googleapis.com/auth/analytics.manage.users,'
        'https://www.googleapis.com/auth/webmasters,'
        'https://www.googleapis.com/auth/cloud-platform"'
    )
    print("  認証完了")

def step2_get_property_ids():
    """GA4 Admin API で数値プロパティIDを取得"""
    print("\n[Step 2] GA4プロパティID取得中...")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import google.auth

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )

        service = build("analyticsadmin", "v1beta", credentials=creds)
        accounts = service.accounts().list().execute()

        property_map = {}

        for account in accounts.get("accounts", []):
            acct_name = account["name"]
            props = service.properties().list(filter=f"parent:{acct_name}").execute()
            for prop in props.get("properties", []):
                # prop["name"] = "properties/123456789"
                numeric_id = prop["name"].split("/")[1]
                display_name = prop.get("displayName", "")
                # measurementId は dataStreams から取得
                streams = service.properties().dataStreams().list(parent=prop["name"]).execute()
                for stream in streams.get("dataStreams", []):
                    meas_id = stream.get("webStreamData", {}).get("measurementId", "")
                    for key, g_id in MEASUREMENT_IDS.items():
                        if meas_id == g_id:
                            property_map[key] = numeric_id
                            print(f"  ✓ {key}: {g_id} → property/{numeric_id} ({display_name})")

        if len(property_map) < len(MEASUREMENT_IDS):
            missing = [k for k in MEASUREMENT_IDS if k not in property_map]
            print(f"  ⚠ 見つからなかったプロパティ: {missing}")
            print("  → 手動で追加が必要かもしれません")

        return property_map

    except Exception as e:
        print(f"  エラー: {e}")
        print("  → プロパティIDを手動設定します")
        return {}

def step3_add_service_account(property_map):
    """GA4各プロパティにサービスアカウントを閲覧者として追加"""
    print(f"\n[Step 3] サービスアカウントをGA4プロパティに追加中...")
    print(f"  SA Email: {SA_EMAIL}")
    try:
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/analytics.manage.users"]
        )
        service = build("analyticsadmin", "v1beta", credentials=creds)

        for key, numeric_id in property_map.items():
            prop_name = f"properties/{numeric_id}"
            body = {
                "roles": ["predefinedRoles/viewer"],
                "user": SA_EMAIL,
            }
            try:
                result = service.properties().accessBindings().create(
                    parent=prop_name, body=body
                ).execute()
                print(f"  ✓ {key} ({prop_name}) に追加完了")
            except Exception as e:
                err_str = str(e)
                if "already exists" in err_str.lower() or "409" in err_str:
                    print(f"  ✓ {key} ({prop_name}) — 既に追加済み")
                else:
                    print(f"  ✗ {key}: {err_str[:100]}")

    except Exception as e:
        print(f"  エラー: {e}")

def step4_check_gsc():
    """GSCプロパティへのアクセス確認"""
    print(f"\n[Step 4] Google Search Consoleプロパティ確認中...")
    try:
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/webmasters"]
        )
        service = build("searchconsole", "v1", credentials=creds)
        sites = service.sites().list().execute()

        accessible_urls = [s.get("siteUrl", "") for s in sites.get("siteEntry", [])]
        print(f"  アクセス可能なGSCプロパティ: {len(accessible_urls)}件")

        for key, url in GSC_URLS.items():
            found = any(url.rstrip("/") in s.rstrip("/") for s in accessible_urls)
            status = "✓" if found else "✗"
            print(f"  {status} {key}: {url}")
            if not found:
                print(f"    → Search Console でサービスアカウント ({SA_EMAIL}) を追加してください")
                print(f"    → 権限: 「制限付き」で OK")

    except Exception as e:
        print(f"  エラー: {e}")

def step5_update_report_py(property_map):
    """report.py の ga4_id を数値プロパティIDに書き換え"""
    print(f"\n[Step 5] report.py を更新中...")
    if not property_map:
        print("  プロパティIDが取得できなかったためスキップ")
        return

    report_path = os.path.join(SCRIPT_DIR, "report.py")
    with open(report_path, "r") as f:
        content = f.read()

    replacements = {
        "camjyo":  '"BSWF4PM45S"',
        "crystal": '"Q9YT04QEHX"',
        "vantrip": '"RC4937NTHC"',
        "jdtlc":   '"EN3734XZMP"',
    }

    updated = content
    for key, numeric_id in property_map.items():
        old_val = replacements.get(key, "")
        if old_val and old_val in updated:
            updated = updated.replace(old_val, f'"{numeric_id}"')
            print(f"  ✓ {key}: → {numeric_id}")

    if updated != content:
        with open(report_path, "w") as f:
            f.write(updated)
        print("  report.py 更新完了")
    else:
        print("  変更なし（既に正しい可能性あり）")

def step6_generate_env():
    """環境変数ファイルを生成"""
    print(f"\n[Step 6] 環境変数ファイルを生成中...")
    env_path = os.path.join(SCRIPT_DIR, ".env")

    # LINE TOKEN
    line_token = input("  LINE Notifyトークンを入力してください (スキップはEnter): ").strip()

    content = f"""# Canjo Analytics Reporter — 環境変数
# 自動生成: setup_auto.py

GOOGLE_APPLICATION_CREDENTIALS={SA_JSON_PATH}
LINE_NOTIFY_TOKEN={line_token}

GSC_CAMJYO=https://www.camjyo.com/
GSC_CRYSTAL=https://crystalinsence.com/
GSC_VANTRIP=https://vantripjapan.jp/
GSC_JDTLC=https://drive-japan-license.com/
"""
    with open(env_path, "w") as f:
        f.write(content)
    print(f"  ✓ {env_path} を生成しました")

def step7_test_run():
    """テスト実行（GA4のみ、LINE送信なし）"""
    print(f"\n[Step 7] テスト実行中...")
    env_path = os.path.join(SCRIPT_DIR, ".env")

    # .env を読み込んで環境変数にセット
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

    # LINE_NOTIFY_TOKEN を空にして送信せずテスト
    os.environ["LINE_NOTIFY_TOKEN"] = ""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_JSON_PATH

    try:
        sys.path.insert(0, SCRIPT_DIR)
        import report
        report.main()
        print("\n  ✅ テスト実行成功！")
    except Exception as e:
        print(f"\n  ✗ エラー: {e}")
        print("  → 上のエラーを確認してください")

def main():
    print("=" * 50)
    print("Canjo Analytics Reporter — 自動セットアップ")
    print("=" * 50)

    # Step 1: ADC認証（ブラウザが開く）
    step1_auth()

    # Step 2: GA4数値プロパティID取得
    property_map = step2_get_property_ids()

    # Step 3: サービスアカウントをGA4プロパティに追加
    if property_map:
        step3_add_service_account(property_map)
    else:
        print("\n[Step 3] スキップ（プロパティIDが不明）")

    # Step 4: GSCアクセス確認
    step4_check_gsc()

    # Step 5: report.py更新
    step5_update_report_py(property_map)

    # Step 6: .env生成
    step6_generate_env()

    # Step 7: テスト実行
    answer = input("\nテスト実行しますか？(y/N): ").strip().lower()
    if answer == "y":
        step7_test_run()

    print("\n" + "=" * 50)
    print("✅ セットアップ完了！")
    print("=" * 50)
    print("\n次のステップ:")
    print("  1. GSCにサービスアカウントを手動追加（Step 4で✗が出た場合）")
    print(f"     SA Email: {SA_EMAIL}")
    print("  2. LINE Notify token が未設定の場合:")
    print("     https://notify-bot.line.me/ja/ でトークンを取得")
    print("  3. 週次自動実行の設定は claude.ai/code/scheduled で完了済み")

if __name__ == "__main__":
    main()
