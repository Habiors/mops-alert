"""
Daily 公開資訊觀測站 (MOPS) 重大訊息 watch, one page per person.

Cloud version, adapted 2026-08-14 from the local MOPSAlertRobot project at
~/Projects/MOPSAlertRobot on Charles's Mac (see that project's CLAUDE.md for
the full history: why the output moved from PDF+Gmail to local HTML, and why
the data source moved from the T-1 open-data gateway to this live endpoint).

**Extended to 5 people 2026-08-16** per Charles: "我之後要給每個人（Eric, ian,
ryan, jun, Charles）個字的mopsalert 請你幫我做出區隔" - was a single page
(Eric's watchlist only). Each person's watchlist is that person's own sibling
robot's TW-listed tier tickers (CharlesRobot/SavvyIanRobot/JunRobot/RyanRobot/
EricRobot's sector_digest.py, pulled 2026-08-16 - a point-in-time snapshot,
not a live link to those repos). **Nick added same day** ("nick呢") -
NickRobot's watchlist (25 tickers, Tier1封測10 + Tier2設備15), pulled from
NickRobot's own sector_digest.py the same way as the other five.

**Charles's watchlist trimmed 2026-08-16** ("remove零組件供應鏈") - this
MOPS-alert watchlist is now his own scoped subset, not a full mirror of
CharlesRobot's sector_digest.py tiers anymore. Dropped the 18-ticker 零組件
供應鏈 category (台達電/緯穎/緯創/PCB-載板/CCL/被動元件/連接器names) entirely -
Charles's MOPS-alert list is now just Tier1 IC設計/控制晶片 + Tier2 光通訊
光學元件 (26 tickers). If CharlesRobot's own sector_digest.py changes later,
don't assume this watchlist should follow - it diverged on purpose.

Migrated to run on GitHub Actions instead of local launchd because the local
version required Charles's laptop to stay powered on and awake through 21:30
every weekday - this runs on GitHub's own infrastructure instead, no local
machine dependency at all. Output is committed to docs/<person>/index.html
(plus a docs/index.html hub page linking to all five) and served by GitHub
Pages, instead of a local file opened with macOS's `open`.

Data source: mopsov.twse.com.tw's live query AJAX endpoint (the same one the
local project's mops_watch.py uses) - POST step=0&TYPEK=sii/otc returns a
capped rolling window (~290 rows) of the most recent disclosures market-wide.
Fetched ONCE per run (not once per person) and filtered five ways in memory -
five people watching overlapping tickers doesn't mean five times the HTTP
calls. Known limitation carried over unchanged: on a heavy-filing day this
could miss something from earlier if pushed out of the window by run time.

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

from html_report import render_hub, render_html

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(HERE, "docs")

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

LIVE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"

_ROW_RE = re.compile(
    r"<td>(\d{4,6})</td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([\d/]+)</td>\s*"
    r"<td[^>]*>([\d:]+)</td>\s*<td[^>]*>(.*?)</td>\s*<td>",
    re.S,
)

# Each person's watchlist = their own sibling robot's TW-listed tier tickers
# (pulled directly from each repo's sector_digest.py on 2026-08-16). US
# tickers (no MOPS filings - not TWSE/TPEx-listed) are excluded: LITE/COHR/
# AAOI/4991-adjacent US names for Charles's Tier2, MU/ENTG for Ryan,
# VRT/BE/CRDO for Eric.
PEOPLE = {
    "charles": {
        "label": "Charles",
        "beat": "IC設計/控制晶片 + 光通訊光學元件",
        "tickers": {
            "2330": "台積電", "2454": "聯發科", "2379": "瑞昱", "3443": "創意",
            "3661": "世芯-KY", "3529": "力旺", "3034": "聯詠", "5269": "祥碩",
            "6526": "達發", "6291": "沛亨", "6415": "矽力*-KY", "6138": "茂達",
            "5274": "信驊",
            "2345": "智邦", "3081": "聯亞", "3105": "穩懋", "6442": "光聖",
            "3491": "昇達科", "3363": "上詮", "3163": "波若威", "4979": "華星光",
            "2455": "全新", "3450": "聯鈞", "7917": "源傑科技", "4971": "IET-KY",
            "4991": "環宇-KY",
        },
    },
    "ian": {
        "label": "Ian",
        "beat": "ODM組裝/電源散熱核心 + 零組件供應鏈",
        "tickers": {
            "3231": "緯創", "6669": "緯穎", "2382": "廣達", "2308": "台達電",
            "6285": "啟碁",
            "3037": "欣興", "8046": "南電", "3189": "景碩", "4958": "臻鼎-KY",
            "2368": "金像電", "2313": "華通",
            "2383": "台光電", "6274": "台燿",
            "2327": "國巨", "2492": "華新科", "3042": "晶技",
            "3533": "嘉澤", "3665": "貿聯-KY", "3653": "健策", "2059": "川湖",
        },
    },
    "jun": {
        "label": "Jun",
        "beat": "半導體核心供應鏈",
        "tickers": {
            "2330": "台積電", "2454": "聯發科", "3443": "創意", "3711": "日月光投控",
            "7769": "鴻勁", "7822": "倍利科", "3131": "弘塑", "5274": "信驊",
            "6147": "頎邦", "6187": "萬潤", "6223": "旺矽", "6515": "穎崴",
            "7734": "印能科技", "7751": "竑騰", "2345": "智邦", "2455": "全新",
            "6442": "光聖", "3081": "聯亞", "2360": "致茂", "5536": "聖暉*",
            "3167": "大量",
        },
    },
    "ryan": {
        "label": "Ryan",
        "beat": "廠務工程 + 記憶體/晶圓代工 + 耗材 + 電機機械",
        "tickers": {
            "2404": "漢唐", "6139": "亞翔", "5536": "聖暉*", "6691": "洋基工程",
            "6944": "兆聯實業", "2330": "台積電", "8299": "群聯", "5289": "宜鼎",
            "6488": "環球晶", "1560": "中砂", "5434": "崇越", "1785": "光洋科",
            "8028": "昇陽半導體",
            "1519": "華城", "7750": "新代", "1590": "亞德客-KY", "2049": "上銀",
            "3587": "閎康",
        },
    },
    "nick": {
        "label": "Nick",
        "beat": "封測(OSAT) + 中小型半導體/PCB設備",
        "tickers": {
            "3711": "日月光投控", "2449": "京元電子", "6257": "矽格", "6147": "頎邦",
            "3264": "欣銓", "6451": "訊芯-KY", "6239": "力成", "6223": "旺矽",
            "6515": "穎崴", "6510": "中華精測",
            "6187": "萬潤", "3131": "弘塑", "7734": "印能科技", "6640": "均華",
            "7751": "竑騰", "4573": "高明鐵", "7856": "漢測", "7728": "光焱科技",
            "3563": "牧德", "3030": "德律", "7822": "倍利科", "2467": "志聖",
            "3167": "大量", "8021": "尖點", "7795": "長廣",
        },
    },
    "eric": {
        "label": "Eric",
        "beat": "散熱 + 電池電源 + 連接器",
        "tickers": {
            "3017": "奇鋐", "6805": "富世達", "3324": "雙鴻", "2486": "一詮",
            "2421": "建準", "8996": "高力", "6831": "邁科", "7892": "元鈦科",
            "3653": "健策",
            "2308": "台達電", "2301": "光寶科", "6781": "AES-KY", "3211": "順達",
            "4931": "新盛力", "6409": "旭隼", "3617": "碩天",
            "3533": "嘉澤", "6715": "嘉基", "3665": "貿聯-KY", "7861": "貝爾威勒",
        },
    },
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


def fetch_all_today_disclosures(today_roc_slash: str) -> list:
    """Fetch once, market-wide - filtering per-person happens later."""
    all_rows = []
    for typek in ("sii", "otc"):
        all_rows.extend(_fetch_live_table(typek))
    # Defensive date filter - the live window should already only contain
    # today, but don't trust that blindly.
    return [r for r in all_rows if r[2] == today_roc_slash]


def _dedup(matches):
    seen = set()
    out = []
    for m in matches:
        key = (m[0], m[2])  # (ticker, subject)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = _taipei_now()
    today_roc_slash = _to_roc_slash(now)
    updated_str = now.strftime("%Y-%m-%d %H:%M")

    today_rows = fetch_all_today_disclosures(today_roc_slash)
    print(f"Fetched {len(today_rows)} market-wide disclosures for {today_roc_slash}.")

    hub_people = []

    for key, person in PEOPLE.items():
        watchlist = person["tickers"]
        matches = [
            (ticker, name or watchlist[ticker], subject, adate)
            for ticker, name, adate, _atime, subject in today_rows
            if ticker in watchlist
        ]
        matches = _dedup(matches)

        print(f"{person['label']}: {len(watchlist)} tickers, {len(matches)} matches.")
        for ticker, name, subject, _ in matches:
            print(f"  {name}（{ticker}）: {subject[:60]}")

        hub_people.append({
            "label": f"{person['label']}（{person['beat']}）",
            "href": f"{key}/",
            "count": len(matches),
        })

        if args.dry_run:
            continue

        disclosures = [
            {"ticker": ticker, "name": name, "subject": subject, "announce_date": adate}
            for ticker, name, subject, adate in matches
        ]

        person_dir = os.path.join(DOCS_DIR, key)
        os.makedirs(person_dir, exist_ok=True)
        output_path = os.path.join(person_dir, "index.html")
        count_label = f"今日重大訊息 · {len(matches)} 則"
        date_str = f"彙整日期：{now.date().isoformat()}　|　最後更新：{updated_str}（台北時間）"

        render_html(output_path, person["label"], "重大訊息公告監控", date_str,
                    count_label, disclosures, back_href="../")

    if args.dry_run:
        print("--dry-run: no HTML written.")
        return

    os.makedirs(DOCS_DIR, exist_ok=True)
    hub_path = os.path.join(DOCS_DIR, "index.html")
    hub_date_str = f"最後更新：{updated_str}（台北時間）"
    render_hub(hub_path, hub_date_str, hub_people)
    print(f"HTML written to docs/ (hub + {len(PEOPLE)} person pages)")


if __name__ == "__main__":
    main()
