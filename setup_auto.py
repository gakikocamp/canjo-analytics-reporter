#!/usr/bin/env python3
"""
Canjo Analytics Reporter — セットアップスクリプト
サービスアカウントを使ってGA4・GSCへの接続テストとレポートを実行します。
"""

import os
import sys
import json

SA_EMAIL = "analytics-reporter@canjo-analytics-reporter.iam.gserviceaccount.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SA_JSON_PATH = os.path.join(SCRIPT_DIR, "service_account.json")

# GA4 測定ID → 数値プロパティID のマッピング
# ※ GA4管理画面 > プロパティ設定 > プロパティID（数値）を確認して入力
PROPERTY_IDS = {
    "camjyo":  "",   # camjyo.com + campconsul  (GA4管理で確認)
    "crystal": "",   # crystalinsence.com
    "vantrip": "",   # vantripjapan.jp
    "jdtlc":   "",   # drive-japan-license.com
}

def step1_instructions():
    print("""
╔══════════════════════════════════════════════════════════╗
║  Canjo Analytics Reporter — サービスアカウント登録手順  ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  サービスアカウント Email:                               ║
║  analytics-reporter@canjo-analytics-reporter             ║
║  .iam.gserviceaccount.com                                ║
║                                                          ║
╠══ GA4 への追加（4プロパティ）══════════════════════════╣
║  1. https://analytics.google.com を開く                  ║
║  2. 左下「管理」→「プロパティのアクセス管理」            ║
║  3. 「＋」→「ユーザーを追加」                           ║
║  4. Email: 上記SA Email を貼り付け                       ║
║  5. ロール: 「閲覧者」                                   ║
║  6. 同時に「プロパティID」（数値）をメモ                 ║
║     管理 > プロパティ設定 > プロパティID                 ║
║                                                          ║
║  対象プロパティ（それぞれ同じ手順）:                     ║
║  - G-BSWF4PM45S (camjyo.com)                            ║
║  - G-Q9YT04QEHX (crystalinsence.com)                    ║
║  - G-RC4937NTHC (vantripjapan.jp)                       ║
║  - G-EN3734XZMP (drive-japan-license.com)               ║
║                                                          ║
╠══ GSC への追加（4プロパティ）══════════════════════════╣
║  1. https://search.google.com/search-console を開く      ║
║  2. 各サイト選択 → 「設定」→「ユーザーと権限」          ║
║  3. 「ユーザーを追加」→ 上記SA Email → 権限「制限付き」 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

def step2_enter_property_ids():
    """GA4 数値プロパティIDを手動入力"""
    print("[Step 2] GA4 数値プロパティIDを入力してください")
    print("  (GA4管理 > プロパティ設定 > プロパティID の数値)\n")

    ids = {}
    sites = [
        ("camjyo",  "camjyo.com + campconsul (G-BSWF4PM45S)"),
        ("crystal", "crystalinsence.com      (G-Q9YT04QEHX)"),
        ("vantrip", "vantripjapan.jp         (G-RC4937NTHC)"),
        ("jdtlc",   "drive-japan-license.com (G-EN3734XZMP)"),
    ]

    for key, label in sites:
        val = input(f"  {label}: ").strip()
        if val:
            ids[key] = val

    return ids

def step3_update_report_py(property_ids):
    """report.py の ga4_id（測定ID末尾）を数値プロパティIDに置換"""
    if not property_ids:
        print("\n[Step 3] スキップ（ID未入力）")
        return

    print("\n[Step 3] report.py を更新中...")
    report_path = os.path.join(SCRIPT_DIR, "report.py")
    with open(report_path, "r") as f:
        content = f.read()

    old_ids = {
        "camjyo":  "BSWF4PM45S",
        "crystal": "Q9YT04QEHX",
        "vantrip": "RC4937NTHC",
        "jdtlc":   "EN3734XZMP",
    }

    updated = content
    for key, numeric_id in property_ids.items():
        old = f'"{old_ids[key]}"'
        new = f'"{numeric_id}"'
        if old in updated:
            updated = updated.replace(old, new)
            print(f"  ✓ {key}: {old_ids[key]} → {numeric_id}")

    if updated != content:
        with open(report_path, "w") as f:
            f.write(updated)
        print("  report.py 更新完了")

def step4_generate_env():
    """環境変数ファイルを生成"""
    print("\n[Step 4] 環境変数ファイルを生成中...")
    env_path = os.path.join(SCRIPT_DIR, ".env")

    print("  LINE Notifyトークンを入力してください")
    print("  取得先: https://notify-bot.line.me/ja/ > マイページ > トークンを発行")
    line_token = input("  LINE_NOTIFY_TOKEN: ").strip()

    content = f"""# Canjo Analytics Reporter — 環境変数

GOOGLE_APPLICATION_CREDENTIALS={SA_JSON_PATH}
LINE_NOTIFY_TOKEN={line_token}

GSC_CAMJYO=https://www.camjyo.com/
GSC_CRYSTAL=https://crystalinsence.com/
GSC_VANTRIP=https://vantripjapan.jp/
GSC_JDTLC=https://drive-japan-license.com/
"""
    with open(env_path, "w") as f:
        f.write(content)
    print(f"  ✓ .env を生成しました")

def step5_test():
    """サービスアカウントでGA4接続テスト"""
    print("\n[Step 5] GA4接続テスト中...")

    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_JSON_PATH
    os.environ["LINE_NOTIFY_TOKEN"] = ""  # 送信しない

    try:
        # report.py を直接実行
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "report.py")],
            capture_output=True, text=True,
            env={**os.environ, "LINE_NOTIFY_TOKEN": ""}
        )
        print(result.stdout[:2000])
        if result.returncode == 0:
            print("\n  ✅ テスト成功！週次レポートが正常に動作しています")
        else:
            print(f"\n  ✗ エラー:\n{result.stderr[:1000]}")
            print("\n  → SAがGA4プロパティに追加されているか確認してください")
    except Exception as e:
        print(f"  エラー: {e}")

def main():
    print("=" * 55)
    print("  Canjo Analytics Reporter — セットアップ")
    print("=" * 55)

    # Step 1: 手順説明
    step1_instructions()
    input("  [Enter] GA4・GSCへのSA追加が完了したら Enter を押してください...")

    # Step 2: プロパティID入力
    property_ids = step2_enter_property_ids()

    # Step 3: report.py更新
    step3_update_report_py(property_ids)

    # Step 4: .env生成
    step4_generate_env()

    # Step 5: テスト
    answer = input("\n接続テストを実行しますか？(Y/n): ").strip().lower()
    if answer != "n":
        step5_test()

    print("\n" + "=" * 55)
    print("✅ セットアップ完了！")
    print("=" * 55)
    print(f"\nサービスアカウント: {SA_EMAIL}")
    print("週次実行: 毎週月曜日 9:00（macOS launchd登録済み）")
    print("ログ: /tmp/canjo-analytics-reporter.log")

if __name__ == "__main__":
    main()
