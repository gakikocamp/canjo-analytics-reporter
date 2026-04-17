#!/usr/bin/env python3
"""
Canjo Analytics Reporter — 全自動セットアップ
ブラウザで1回Googleログインするだけで全設定完了。
"""

import os, sys, json, pickle, subprocess
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent.resolve()
SA_EMAIL    = "analytics-reporter@canjo-analytics-reporter.iam.gserviceaccount.com"
SA_JSON     = SCRIPT_DIR / "service_account.json"
CREDS_JSON  = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/開発用/SecondGaki/高城剛/メールアーカイブ/credentials.json"
TOKEN_CACHE = SCRIPT_DIR / ".oauth_token.pickle"
REPORT_PY   = SCRIPT_DIR / "report.py"
ENV_FILE    = SCRIPT_DIR / ".env"

GA4_MEASUREMENT_IDS = {
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

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.manage.users",
    "https://www.googleapis.com/auth/webmasters",
]

# ─── 依存チェック ──────────────────────────────────────
def ensure_deps():
    missing = []
    for pkg in ["google_auth_oauthlib", "googleapiclient"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg.replace("_", "-"))
    if missing:
        print(f"  パッケージをインストール中: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "google-auth-oauthlib", "google-api-python-client", "-q"])

# ─── Step 1: OAuth認証（独自クライアント）─────────────
def get_credentials():
    print("\n[Step 1] Google認証 (ブラウザが1回開きます)")

    if TOKEN_CACHE.exists():
        with open(TOKEN_CACHE, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.valid:
            print("  ✓ 保存済みトークンを使用")
            return creds
        if creds and creds.expired:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_CACHE, "wb") as f:
                pickle.dump(creds, f)
            print("  ✓ トークンを更新しました")
            return creds

    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_JSON), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    with open(TOKEN_CACHE, "wb") as f:
        pickle.dump(creds, f)
    print("  ✓ 認証完了・トークン保存済み")
    return creds

# ─── Step 2: GA4プロパティID自動取得 ──────────────────
def get_property_ids(creds):
    print("\n[Step 2] GA4プロパティIDを自動取得中...")
    from googleapiclient.discovery import build

    service = build("analyticsadmin", "v1beta", credentials=creds)
    accounts = service.accounts().list().execute().get("accounts", [])

    id_map = {}
    for acct in accounts:
        props = service.properties().list(
            filter=f"parent:{acct['name']}"
        ).execute().get("properties", [])

        for prop in props:
            numeric_id = prop["name"].split("/")[1]
            streams = service.properties().dataStreams().list(
                parent=prop["name"]
            ).execute().get("dataStreams", [])
            for stream in streams:
                meas_id = stream.get("webStreamData", {}).get("measurementId", "")
                for key, g_id in GA4_MEASUREMENT_IDS.items():
                    if meas_id == g_id:
                        id_map[key] = numeric_id
                        name = prop.get("displayName", "")
                        print(f"  ✓ {key}: {g_id} → {numeric_id} ({name})")

    missing = [k for k in GA4_MEASUREMENT_IDS if k not in id_map]
    if missing:
        print(f"  ⚠ 見つからず: {missing} — 手動で入力してください")
        for key in missing:
            val = input(f"    {key} の数値プロパティID: ").strip()
            if val:
                id_map[key] = val
    return id_map

# ─── Step 3: サービスアカウントをGA4へ自動追加 ────────
def add_sa_to_ga4(creds, id_map):
    print(f"\n[Step 3] サービスアカウントをGA4に追加中...")
    from googleapiclient.discovery import build

    service = build("analyticsadmin", "v1beta", credentials=creds)
    for key, numeric_id in id_map.items():
        parent = f"properties/{numeric_id}"
        body = {"roles": ["predefinedRoles/viewer"], "user": SA_EMAIL}
        try:
            service.properties().accessBindings().create(
                parent=parent, body=body
            ).execute()
            print(f"  ✓ {key} ({numeric_id}) に追加完了")
        except Exception as e:
            if "409" in str(e) or "already" in str(e).lower():
                print(f"  ✓ {key} — 既に追加済み")
            else:
                print(f"  ✗ {key}: {str(e)[:80]}")

# ─── Step 4: GSCアクセス確認 ──────────────────────────
def check_gsc(creds):
    print(f"\n[Step 4] Google Search Console アクセス確認中...")
    from googleapiclient.discovery import build

    service = build("searchconsole", "v1", credentials=creds)
    sites = service.sites().list().execute()
    accessible = [s.get("siteUrl", "") for s in sites.get("siteEntry", [])]

    all_ok = True
    for key, url in GSC_URLS.items():
        found = any(url.rstrip("/") in s.rstrip("/") for s in accessible)
        if found:
            print(f"  ✓ {key}: アクセス可能")
        else:
            print(f"  ✗ {key} ({url}): 未登録")
            print(f"    → Search Console > 設定 > ユーザーと権限 > 追加")
            print(f"    → Email: {SA_EMAIL} / 権限: 制限付き")
            all_ok = False

    if not all_ok:
        input("\n  GSCへの追加が完了したら Enter を押してください...")
    return all_ok

# ─── Step 5: report.py を数値プロパティIDに更新 ────────
def update_report_py(id_map):
    print(f"\n[Step 5] report.py を更新中...")
    old_ids = {
        "camjyo":  "BSWF4PM45S",
        "crystal": "Q9YT04QEHX",
        "vantrip": "RC4937NTHC",
        "jdtlc":   "EN3734XZMP",
    }
    content = REPORT_PY.read_text()
    updated = content
    for key, numeric_id in id_map.items():
        old_str = f'"{old_ids[key]}"'
        new_str = f'"{numeric_id}"'
        if old_str in updated:
            updated = updated.replace(old_str, new_str)
            print(f"  ✓ {key}: → {numeric_id}")
    if updated != content:
        REPORT_PY.write_text(updated)
        print("  report.py 保存完了")

# ─── Step 6: .env 生成 ─────────────────────────────────
def generate_env():
    print(f"\n[Step 6] 環境変数ファイルを生成中...")
    print("  LINE Notifyトークンが必要です。")
    print("  取得先: https://notify-bot.line.me/ja/ > マイページ > トークンを発行")
    line_token = input("  LINE_NOTIFY_TOKEN (スキップはEnter): ").strip()

    ENV_FILE.write_text(f"""# Canjo Analytics Reporter
GOOGLE_APPLICATION_CREDENTIALS={SA_JSON}
LINE_NOTIFY_TOKEN={line_token}
GSC_CAMJYO=https://www.camjyo.com/
GSC_CRYSTAL=https://crystalinsence.com/
GSC_VANTRIP=https://vantripjapan.jp/
GSC_JDTLC=https://drive-japan-license.com/
""")
    print("  ✓ .env 生成完了")

# ─── Step 7: 接続テスト ───────────────────────────────
def test_run():
    print(f"\n[Step 7] 接続テスト中（LINE送信なし）...")
    env = {**os.environ,
           "GOOGLE_APPLICATION_CREDENTIALS": str(SA_JSON),
           "LINE_NOTIFY_TOKEN": ""}
    # .env を読み込む
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env["LINE_NOTIFY_TOKEN"] = ""  # 送信しない

    result = subprocess.run(
        [sys.executable, str(REPORT_PY)],
        capture_output=True, text=True, env=env
    )
    print(result.stdout[:3000])
    if result.returncode == 0:
        print("\n  ✅ 接続テスト成功！週次レポートが正常に動作しています")
    else:
        print(f"\n  ✗ エラー:\n{result.stderr[:1000]}")

# ─── メイン ───────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Canjo Analytics Reporter — 全自動セットアップ")
    print("=" * 55)

    ensure_deps()

    # Step 1: OAuth（ブラウザで1回ログイン）
    creds = get_credentials()

    # Step 2: GA4プロパティID自動取得
    id_map = get_property_ids(creds)

    # Step 3: SAをGA4に自動追加
    add_sa_to_ga4(creds, id_map)

    # Step 4: GSCアクセス確認
    check_gsc(creds)

    # Step 5: report.py更新
    update_report_py(id_map)

    # Step 6: .env生成
    generate_env()

    # Step 7: テスト
    if input("\n接続テストを実行しますか？(Y/n): ").strip().lower() != "n":
        test_run()

    print("\n" + "=" * 55)
    print("✅ セットアップ完了！")
    print("=" * 55)
    print("週次実行: 毎週月曜日 9:00（macOS launchd登録済み）")
    print("ログ: /tmp/canjo-analytics-reporter.log")

if __name__ == "__main__":
    main()
