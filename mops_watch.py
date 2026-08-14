"""
Daily 公開資訊觀測站 (MOPS) 重大訊息 watch, filtered to Charles's watchlist.
Cloud version, adapted 2026-08-14 from the local MOPSAlertRobot project at
~/Projects/MOPSAlertRobot on Charles's Mac (see that project's CLAUDE.md for
the full history: why the output moved from PDF+Gmail to local HTML, and why
the data source moved from the T-1 open-data gateway to this live endpoint).

Migrated to run on GitHub Actions instead of local launchd because the local
version required Charles's laptop to stay powered on and awake through 21:30
every weekday - this runs on GitHub's own infrastructure instead, no local
machine dependency at all. Output is committed to docs/index.html and served
by GitHub Pages, instead of a local file opened with macOS's `open`.

Data source: mopsov.twse.com.tw's live query AJAX endpoint (the same one the
local project's mops_watch.py uses) - POST step=0&TYPEK=sii/otc returns a
capped rolling window (~290 rows) of the most recent disclosures market-wide.
Known limitation carried over unchanged: on a heavy-filing day this could
miss something from earlier if pushed out of the window by run time.

Usage:
    python3 mops_watch.py [--dry-run]
"""
import argparse
import os
import re
import ssl
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import certifi

from html_report import render_html

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(HERE, "docs")

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

LIVE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"

_ROW_RE = re.compile(
    r"<td>(\d{4,6})</td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([\d/]+)</td>\s*"
    r"<td[^>]*>([\d:]+)</td>\s*<td[^>]*>(.*?)</td>\s*<td>",
    re.S,
)

# Same watchlist as the local project (EricRobot's TW-listed tickers,
# 2026-08-13 snapshot) - kept in sync manually, not a live link.
WATCHLIST = {
    "3017": "奇鋐", "6805": "富世達", "3324": "雙鴻", "2486": "一詮",
    "2421": "建準", "8996": "高力", "6831": "邁科", "7892": "元鈦科",
    "3653": "健策",
    "2308": "台達電", "2301": "光寶科", "6781": "AES-KY", "3211": "順達",
    "4931": "新盛力", "6409": "旭隼", "3617": "碩天",
    "3533": "嘉澤", "6715": "嘉基", "3665": "貿聯-KY", "7861": "貝爾威勒",
}


def _taipei_now() -> datetime:
    # Python's zoneinfo instead of shelling out to `date` - the local
    # project's _taipei_today() used a subprocess call because it needed to
    # override a Mac's auto-following system timezone; a GitHub Actions
    # runner has no such concern (it's not "traveling"), so plain zoneinfo
    # is simpler and doesn't need a `date` binary on PATH.
    return datetime.now(ZoneInfo("Asia/Taipei"))


def _to_roc_slash(dt: datetime) -> str:
    return f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"


def _fetch_live_table(typek: str) -> list:
    """typek: 'sii' (TWSE) or 'otc' (TPEx)."""
    req = urllib.request.Request(
        LIVE_URL,
        data=f"step=0&TYPEK={typek}".encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
        html_text = resp.read().decode("utf-8", errors="replace")
    rows = []
    for m in _ROW_RE.finditer(html_text):
        ticker, name, adate, atime, subject = m.groups()
        subject = re.sub(r"\s+", " ", subject).strip()
        rows.append((ticker, name.strip(), adate, atime, subject))
    return rows


def fetch_today_disclosures(today_roc_slash: str) -> list:
    matches = []
    for typek in ("sii", "otc"):
        for ticker, name, adate, _atime, subject in _fetch_live_table(typek):
            if ticker in WATCHLIST and adate == today_roc_slash:
                matches.append((ticker, name or WATCHLIST[ticker], subject, adate))
    return matches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = _taipei_now()
    today_roc_slash = _to_roc_slash(now)

    matches = fetch_today_disclosures(today_roc_slash)
    seen = set()
    deduped = []
    for m in matches:
        key = (m[0], m[2])
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    matches = deduped

    print(f"Watchlist: {len(WATCHLIST)} tickers. Today (ROC): {today_roc_slash}. "
          f"Matches: {len(matches)}.")
    for ticker, name, subject, _ in matches:
        print(f"  {name}（{ticker}）: {subject[:60]}")

    if args.dry_run:
        print("--dry-run: no HTML written.")
        return

    disclosures = [
        {"ticker": ticker, "name": name, "subject": subject, "announce_date": adate}
        for ticker, name, subject, adate in matches
    ]

    os.makedirs(DOCS_DIR, exist_ok=True)
    output_path = os.path.join(DOCS_DIR, "index.html")
    count_label = f"今日重大訊息 · {len(matches)} 則"
    updated_str = now.strftime("%Y-%m-%d %H:%M")
    date_str = f"彙整日期：{now.date().isoformat()}　|　最後更新：{updated_str}（台北時間）"

    render_html(output_path, "重大訊息公告監控", date_str, count_label, disclosures)
    print(f"HTML written to {output_path}")


if __name__ == "__main__":
    main()
