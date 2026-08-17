"""
Daily 公開資訊觀測站 (MOPS) 重大訊息 watch, one page per person.

Cloud version, adapted 2026-08-14 from the local MOPSAlertRobot project at
~/Projects/MOPSAlertRobot on Charles's Mac (see that project's CLAUDE.md for
the full history: why the output moved from PDF+Gmail to local HTML, and why
the data source moved from the T-1 open-data gateway to this live endpoint).

**Extended to 5 people 2026-08-16** per Charles: "我之後要給每個人（Eric, ian,
ryan, jun, Charles）個字的mopsalert 請你幫我做出區隔" - was a single page
(Eric's watchlist only). Each person's watchlist is that person's own sibling
robot's TW-listed tier tickers (CharlesRobot/SavvyIanRobot/JyunRobot/RyanRobot/
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

**JunRobot renamed to JyunRobot, same day** ("Junrobot以後幫我改為
JyunRobot") - a full rename (project directory, launchd job, output
filenames, and this page's key/label all changed from Jun/jun to Jyun/jyun).
Historical PDFs already produced under the old `MorningReport_Jun_*.pdf`
naming were NOT renamed - only things going forward use Jyun.

Migrated to run on GitHub Actions instead of local launchd because the local
version required Charles's laptop to stay powered on and awake through 21:30
every weekday - this runs on GitHub's own infrastructure instead, no local
machine dependency at all. Output is committed to docs/<person>/index.html
(plus a docs/index.html hub page linking to all five) and served by GitHub
Pages, instead of a local file opened with macOS's `open`.

Data source: mopsov.twse.com.tw's live query AJAX endpoint (the same one the
local project's mops_watch.py uses) - POST step=0&TYPEK=sii/otc returns a
capped rolling window (~290 rows) of the most recent disclosures market-wide.
Fetched ONCE per run (not once per person) and filtered six ways in memory -
six people watching overlapping tickers doesn't mean six times the HTTP calls.

**Polling frequency raised + accumulation added, 2026-08-16** per Charles
("那提高抓取頻率 在14:00, 15:00, 16:00, 17:00, 18:00, 21:30 各抓一次 並即時
更新，保留當日的重大訊息"), after he asked why the ~290-row cap couldn't just
be raised to 590 - tested several plausible parameter names (rows/pageSize/
cnt/num) against the live endpoint and none changed the row count, so the
cap looks server-side and not client-controllable. The actual fix: run six
times a day instead of once, and CARRY FORWARD each day's findings across
runs rather than each run only showing whatever's in the buffer at that
moment - a disclosure that was visible at 14:00 but gets pushed out of the
290-row window by 16:00 must still show up on the 16:00-21:30 pages.

Since each run is a fresh GitHub Actions VM (no memory of earlier runs),
accumulation needs real persistence - `state/<YYYY-MM-DD>.json` is committed
back to the repo each run (see the workflow's "Commit state" step), holding
every match found so far today per person. Each run: load today's state (or
start empty if this is the day's first run) -> fetch live -> merge new
matches into the existing accumulated set (deduped, same as before) -> save
state -> render HTML from the ACCUMULATED set, not just this run's fetch.
State files older than a week are pruned each run (see _prune_old_state) -
they're tiny and only useful for the same day, no reason to keep piling up.

Usage:
    python3 mops_watch.py [--dry-run]
"""
import argparse
import glob
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import certifi

from html_report import render_hub, render_html

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(HERE, "docs")
STATE_DIR = os.path.join(HERE, "state")
STATE_MAX_AGE_DAYS = 7

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

LIVE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"

_ROW_RE = re.compile(
    r"<td>(\d{4,6})</td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([\d/]+)</td>\s*"
    r"<td[^>]*>([\d:]+)</td>\s*<td[^>]*>(.*?)</td>\s*<td>\s*"
    r"<input[^>]*onclick=\"([^\"]*)\"",
    re.S,
)

# Each row's "詳細資料" button doesn't link anywhere - clicking it runs this
# inline JS, which fills these hidden form fields on the page's own <form>
# and re-POSTs it (see mops2.js's openWindow()) to fetch the full disclosure
# text. Added 2026-08-17 per Charles ("我需要的就是連接到這個按鈕之後的網頁") -
# confirmed by direct testing that POSTing these same fields to LIVE_URL with
# step=1 returns the detail page, so a plain auto-submitting <form> (no JS)
# reproduces the same click without needing to touch MOPS's own script.
_ONCLICK_FIELD_RE = re.compile(
    r"\.(SEQ_NO|SPOKE_TIME|SPOKE_DATE|COMPANY_ID|skey)\.value='([^']*)'"
)


def _parse_detail(onclick: str, typek: str) -> dict | None:
    fields = dict(_ONCLICK_FIELD_RE.findall(onclick))
    required = ("SEQ_NO", "SPOKE_TIME", "SPOKE_DATE", "COMPANY_ID", "skey")
    if not all(f in fields for f in required):
        return None  # unexpected onclick shape - degrade to no-link rather than crash
    return {
        "typek": typek,
        "seq_no": fields["SEQ_NO"],
        "spoke_time": fields["SPOKE_TIME"],
        "spoke_date": fields["SPOKE_DATE"],
        "company_id": fields["COMPANY_ID"],
        "skey": fields["skey"],
    }

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
    "jyun": {
        "label": "Jyun",
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
            "3587": "閎康", "8996": "高力",
        },
    },
    "nick": {
        "label": "Nick",
        "beat": "封測+設備",
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
            "2421": "建準", "6831": "邁科", "7892": "元鈦科",
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


def _fetch_live_table(typek: str, attempts: int = 3) -> list:
    """typek: 'sii' (TWSE) or 'otc' (TPEx).

    Retries on transient failures (added 2026-08-16 after a real one-off
    HTTP 307 from GitHub's runner IP - confirmed intermittent, not a
    persistent geo-block, by re-testing the same request from Charles's Mac
    seconds later and getting a normal 200. Now that this runs 6x/day and
    accumulation depends on each run actually succeeding, a single transient
    hiccup shouldn't cost an entire polling slot if a quick retry would fix
    it - this is NOT a fix for a real block, just resilience against noise."""
    req = urllib.request.Request(
        LIVE_URL,
        data=f"step=0&TYPEK={typek}".encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
                html_text = resp.read().decode("utf-8", errors="replace")
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            print(f"  _fetch_live_table({typek}): attempt {attempt}/{attempts} "
                  f"failed ({exc}), retrying..." if attempt < attempts else
                  f"  _fetch_live_table({typek}): attempt {attempt}/{attempts} failed ({exc}), giving up.")
            if attempt < attempts:
                time.sleep(5)
    else:
        raise last_exc

    rows = []
    for m in _ROW_RE.finditer(html_text):
        ticker, name, adate, atime, subject, onclick = m.groups()
        subject = re.sub(r"\s+", " ", subject).strip()
        detail = _parse_detail(onclick, typek)
        rows.append((ticker, name.strip(), adate, atime, subject, detail))
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


def _state_path(today_iso: str) -> str:
    return os.path.join(STATE_DIR, f"{today_iso}.json")


def _load_state(today_iso: str) -> dict:
    """Returns {person_key: [[ticker, name, subject, announce_date, detail], ...]}
    (older entries may only have 4 elements - see main()'s padding step).
    Empty dict if no state file exists yet for today (this run is the day's
    first, or the file was pruned/never committed)."""
    path = _state_path(today_iso)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_state(today_iso: str, state: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(_state_path(today_iso), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def _prune_old_state(today: datetime) -> None:
    if not os.path.isdir(STATE_DIR):
        return
    cutoff = today.date() - timedelta(days=STATE_MAX_AGE_DAYS)
    for path in glob.glob(os.path.join(STATE_DIR, "*.json")):
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            file_date = datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            continue  # not one of ours, leave it alone
        if file_date < cutoff:
            os.remove(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = _taipei_now()
    today_iso = now.date().isoformat()
    today_roc_slash = _to_roc_slash(now)
    updated_str = now.strftime("%Y-%m-%d %H:%M")

    today_rows = fetch_all_today_disclosures(today_roc_slash)
    print(f"Fetched {len(today_rows)} market-wide disclosures for {today_roc_slash}.")

    if not args.dry_run:
        _prune_old_state(now)
    state = _load_state(today_iso)

    hub_people = []

    for key, person in PEOPLE.items():
        watchlist = person["tickers"]
        new_matches = [
            (ticker, name or watchlist[ticker], subject, adate, detail)
            for ticker, name, adate, _atime, subject, detail in today_rows
            if ticker in watchlist
        ]

        # Accumulate: today's carried-forward state (from earlier runs today)
        # plus whatever this run just found, deduped. A disclosure visible
        # at 14:00 but pushed out of the live buffer by 18:00 must still
        # show up here - that's the whole point of persisting state.
        # Pad older 4-element state entries (saved before the 2026-08-17
        # detail-link field was added) with detail=None so they still
        # unpack correctly - they just render without a "查看原始公告" link.
        previous = []
        for m in state.get(key, []):
            if len(m) == 4:
                m = list(m) + [None]
            previous.append(tuple(m))
        matches = _dedup(previous + new_matches)
        state[key] = [list(m) for m in matches]

        print(f"{person['label']}: {len(watchlist)} tickers, "
              f"{len(new_matches)} in this fetch, {len(matches)} accumulated today.")
        for ticker, name, subject, _adate, _detail in matches:
            print(f"  {name}（{ticker}）: {subject[:60]}")

        hub_people.append({
            "label": f"{person['label']}（{person['beat']}）",
            "href": f"{key}/",
            "count": len(matches),
        })

        if args.dry_run:
            continue

        disclosures = [
            {"ticker": ticker, "name": name, "subject": subject, "announce_date": adate,
             "detail": detail}
            for ticker, name, subject, adate, detail in matches
        ]

        person_dir = os.path.join(DOCS_DIR, key)
        os.makedirs(person_dir, exist_ok=True)
        output_path = os.path.join(person_dir, "index.html")
        count_label = f"今日重大訊息（累計）· {len(matches)} 則"
        date_str = f"彙整日期：{today_iso}　|　最後更新：{updated_str}（台北時間）"

        render_html(output_path, person["label"], "重大訊息公告監控", date_str,
                    count_label, disclosures, back_href="../")

    if args.dry_run:
        print("--dry-run: no HTML written, no state saved.")
        return

    _save_state(today_iso, state)

    os.makedirs(DOCS_DIR, exist_ok=True)
    hub_path = os.path.join(DOCS_DIR, "index.html")
    hub_date_str = f"最後更新：{updated_str}（台北時間）"
    render_hub(hub_path, hub_date_str, hub_people)
    print(f"HTML written to docs/ (hub + {len(PEOPLE)} person pages), state saved.")


if __name__ == "__main__":
    main()
