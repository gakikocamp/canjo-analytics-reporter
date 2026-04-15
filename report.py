"""
CRYSTAL INCENSE / キャンジョ グループ
週次 GA4 + GSC 自動レポーター

対象サイト:
  1. キャンジョ コーポレート + キャンプコンサル (G-BSWF4PM45S)
  2. CRYSTAL INCENSE                            (G-Q9YT04QEHX)
  3. VANTRIP JAPAN                              (G-RC4937NTHC)
  4. JDTLC / drive-japan-license.com           (G-EN3734XZMP)

必要な環境変数:
  GOOGLE_APPLICATION_CREDENTIALS  ... サービスアカウントJSON のパス
  LINE_NOTIFY_TOKEN                ... LINE Notify トークン
  GSC_CAMJYO                       ... GSCプロパティURL (例: https://www.camjyo.com/)
  GSC_CRYSTAL                      ... GSCプロパティURL
  GSC_VANTRIP                      ... GSCプロパティURL
  GSC_JDTLC                        ... GSCプロパティURL
"""

import os
import json
import requests
from datetime import date, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Metric, Dimension, OrderBy
)
from googleapiclient.discovery import build
from google.oauth2 import service_account

# ━━━ 設定 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SITES = [
    {
        "name": "🏕 キャンジョ コーポレート + キャンプコンサル",
        "ga4_id": "BSWF4PM45S",          # G- を除いた値
        "gsc_url": os.getenv("GSC_CAMJYO", "https://www.camjyo.com/"),
        "url": "https://www.camjyo.com/",
    },
    {
        "name": "🪔 CRYSTAL INCENSE",
        "ga4_id": "Q9YT04QEHX",
        "gsc_url": os.getenv("GSC_CRYSTAL", "https://crystalinsence.com/"),
        "url": "https://crystalinsence.com/",
    },
    {
        "name": "🚐 VANTRIP JAPAN",
        "ga4_id": "RC4937NTHC",
        "gsc_url": os.getenv("GSC_VANTRIP", "https://vantripjapan.jp/"),
        "url": "https://vantripjapan.jp/",
    },
    {
        "name": "🚗 JDTLC (drive-japan-license.com)",
        "ga4_id": "EN3734XZMP",
        "gsc_url": os.getenv("GSC_JDTLC", "https://drive-japan-license.com/"),
        "url": "https://drive-japan-license.com/",
    },
]

LINE_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")
CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# ━━━ 日付範囲 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_date_ranges():
    today = date.today()
    # 直近7日（今週）
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    # 前週（比較用）
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return (
        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
        prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"),
    )

# ━━━ GA4 データ取得 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_ga4_data(property_id: str, start: str, end: str, prev_start: str, prev_end: str) -> dict:
    if not property_id:
        return {}
    client = BetaAnalyticsDataClient()

    def run(s, e):
        req = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
            ],
            date_ranges=[DateRange(start_date=s, end_date=e)],
        )
        return client.run_report(req)

    def top_pages(s, e):
        req = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="bounceRate"),
            ],
            date_ranges=[DateRange(start_date=s, end_date=e)],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=5,
        )
        return client.run_report(req)

    curr = run(start, end)
    prev = run(prev_start, prev_end)
    pages = top_pages(start, end)

    # 集計
    def sum_metrics(resp):
        totals = {"sessions": 0, "users": 0, "bounce": 0.0, "duration": 0.0, "channels": {}}
        for row in resp.rows:
            ch = row.dimension_values[0].value
            s_val = int(row.metric_values[0].value)
            u_val = int(row.metric_values[1].value)
            b_val = float(row.metric_values[2].value)
            d_val = float(row.metric_values[3].value)
            totals["sessions"] += s_val
            totals["users"] += u_val
            totals["channels"][ch] = {"sessions": s_val, "users": u_val}
        if totals["sessions"] > 0:
            totals["bounce"] = b_val
            totals["duration"] = d_val
        return totals

    curr_data = sum_metrics(curr)
    prev_data = sum_metrics(prev)

    top = []
    for row in pages.rows:
        top.append({
            "path": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "bounce": float(row.metric_values[1].value),
        })

    return {"curr": curr_data, "prev": prev_data, "top_pages": top}

# ━━━ GSC データ取得 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_gsc_data(site_url: str, start: str, end: str) -> dict:
    if not site_url:
        return {}
    creds = service_account.Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("searchconsole", "v1", credentials=creds)

    # 総合パフォーマンス
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["query"],
        "rowLimit": 10,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
    }
    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()

    # ページ別
    page_body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["page"],
        "rowLimit": 5,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
    }
    page_resp = service.searchanalytics().query(siteUrl=site_url, body=page_body).execute()

    top_queries = []
    total_clicks = 0
    total_impressions = 0
    total_ctr = 0.0
    total_position = 0.0

    rows = resp.get("rows", [])
    for row in rows:
        total_clicks += row.get("clicks", 0)
        total_impressions += row.get("impressions", 0)
        top_queries.append({
            "query": row["keys"][0],
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0) * 100, 1),
            "position": round(row.get("position", 0), 1),
        })

    if rows:
        total_ctr = round(sum(r.get("ctr", 0) for r in rows) / len(rows) * 100, 1)
        total_position = round(sum(r.get("position", 0) for r in rows) / len(rows), 1)

    top_pages = []
    for row in page_resp.get("rows", []):
        top_pages.append({
            "page": row["keys"][0].replace(site_url, "/"),
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0) * 100, 1),
            "position": round(row.get("position", 0), 1),
        })

    return {
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": total_ctr,
        "avg_position": total_position,
        "top_queries": top_queries,
        "top_pages": top_pages,
    }

# ━━━ レポート文字列生成 ━━━━━━━━━━━━━━━━━━━━━━━━━━

def pct_change(curr, prev):
    if prev == 0:
        return "+∞%" if curr > 0 else "0%"
    diff = (curr - prev) / prev * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}%"

def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}分{s}秒"

def build_report(site: dict, ga4: dict, gsc: dict, start: str, end: str) -> str:
    lines = []
    lines.append(f"\n{'='*40}")
    lines.append(f"{site['name']}")
    lines.append(f"期間: {start} 〜 {end}")
    lines.append(f"{'='*40}")

    # GA4
    if ga4:
        c = ga4["curr"]
        p = ga4["prev"]
        lines.append("\n【GA4 アクセス概要】")
        lines.append(f"  セッション数  : {c['sessions']:,}  ({pct_change(c['sessions'], p['sessions'])})")
        lines.append(f"  ユーザー数    : {c['users']:,}  ({pct_change(c['users'], p['users'])})")
        lines.append(f"  直帰率        : {c['bounce']*100:.1f}%")
        lines.append(f"  平均滞在時間  : {format_duration(c['duration'])}")

        lines.append("\n  流入チャネル内訳:")
        for ch, val in sorted(c["channels"].items(), key=lambda x: -x[1]["sessions"]):
            lines.append(f"    {ch}: {val['sessions']:,} セッション")

        lines.append("\n  上位ページ (セッション順):")
        for p_item in ga4["top_pages"]:
            lines.append(f"    {p_item['path']}  {p_item['sessions']:,}件 / 直帰率{p_item['bounce']*100:.0f}%")
    else:
        lines.append("\n【GA4】設定未完了")

    # GSC
    if gsc:
        lines.append("\n【Google Search Console】")
        lines.append(f"  クリック数    : {gsc['total_clicks']:,}")
        lines.append(f"  インプレッション: {gsc['total_impressions']:,}")
        lines.append(f"  平均CTR       : {gsc['avg_ctr']}%")
        lines.append(f"  平均掲載順位  : {gsc['avg_position']}位")

        lines.append("\n  上位クエリ (クリック順):")
        for q in gsc["top_queries"][:8]:
            lines.append(f"    [{q['position']}位] {q['query']}")
            lines.append(f"         Click:{q['clicks']} Imp:{q['impressions']} CTR:{q['ctr']}%")

        lines.append("\n  上位ページ (クリック順):")
        for pg in gsc["top_pages"]:
            lines.append(f"    {pg['page']}  Click:{pg['clicks']} 順位:{pg['position']}位")
    else:
        lines.append("\n【GSC】設定未完了")

    return "\n".join(lines)

# ━━━ LINE Notify 送信 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_line(message: str):
    if not LINE_TOKEN:
        print("[LINE] トークン未設定 - コンソール出力のみ")
        print(message)
        return
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    # LINE Notifyは1回2000文字制限 → 分割送信
    chunk_size = 1900
    for i in range(0, len(message), chunk_size):
        chunk = message[i:i+chunk_size]
        requests.post(url, headers=headers, data={"message": chunk})
        print(f"[LINE] 送信済み ({i}〜{i+len(chunk)}文字)")

# ━━━ メイン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    start, end, prev_start, prev_end = get_date_ranges()
    print(f"[週次レポート] {start} 〜 {end} / 比較: {prev_start} 〜 {prev_end}")

    header = (
        f"\n🌿 週次レポート ({start} 〜 {end})\n"
        f"Canjo Group — GA4 + GSC 自動分析"
    )
    full_report = header

    for site in SITES:
        if not site["ga4_id"] and not site["gsc_url"]:
            print(f"[SKIP] {site['name']} — 設定なし")
            continue

        print(f"[取得中] {site['name']}")
        try:
            ga4 = get_ga4_data(site["ga4_id"], start, end, prev_start, prev_end)
        except Exception as e:
            print(f"  GA4エラー: {e}")
            ga4 = {}

        try:
            gsc = get_gsc_data(site["gsc_url"], start, end)
        except Exception as e:
            print(f"  GSCエラー: {e}")
            gsc = {}

        full_report += build_report(site, ga4, gsc, start, end)

    full_report += "\n\n📊 レポート終了\n改善提案は翌朝 Claude Code から送信されます。"

    send_line(full_report)
    print("\n✅ 完了")

if __name__ == "__main__":
    main()
