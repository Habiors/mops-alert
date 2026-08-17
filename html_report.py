"""
HTML renderer for the mops-alert cloud pages.

Extended 2026-08-16 per Charles: "我之後要給每個人（Eric, ian, ryan, jun,
Charles）個字的mopsalert 請你幫我做出區隔" - was a single shared page
(Eric's watchlist only), now renders one page per person plus a hub/landing
page linking to all five. Same look across every page (own <style> block, no
external assets, light/dark via prefers-color-scheme) - the whole point of a
static site hosted on GitHub Pages.
"""
import html as _html

_CSS = """
:root {
  --paper: #f6f4ef;
  --paper-raised: #fbfaf6;
  --ink: #1c1e22;
  --ink-soft: #3a3d42;
  --muted: #6e7178;
  --line: #ddd9ce;
  --accent: #4f5c8a;
  --font-display: Charter, "Iowan Old Style", "Source Serif Pro", Georgia, serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #15181b; --paper-raised: #1b1e22; --ink: #e9e6df; --ink-soft: #c7c4bc;
    --muted: #9b9e9c; --line: #2b2e31; --accent: #7d8ab8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--font-body); font-size: 16px; line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 700px; margin: 0 auto; padding: 44px 24px 90px; }
header { padding-bottom: 20px; margin-bottom: 26px; border-bottom: 2px solid var(--ink); }
.brand { font-family: var(--font-mono); font-size: 11.5px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 6px; }
.backlink { font-family: var(--font-mono); font-size: 12px; margin-bottom: 14px; }
.backlink a { color: var(--accent); text-decoration: none; }
.backlink a:hover { text-decoration: underline; }
h1 { font-family: var(--font-display); font-weight: 600; font-size: 28px; margin: 0 0 8px; }
.meta { font-family: var(--font-mono); font-size: 12.5px; color: var(--muted); }
.count { font-family: var(--font-mono); font-size: 12px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }
.card {
  background: var(--paper-raised); border: 1px solid var(--line);
  border-left: 3px solid var(--accent); border-radius: 8px;
  padding: 16px 18px; margin-bottom: 12px;
}
.card .co { font-weight: 700; font-size: 15.5px; margin-bottom: 4px; }
.card .co .code { font-family: var(--font-mono); font-weight: 400; color: var(--muted); font-size: 12.5px; margin-left: 4px; }
.card .subject { font-size: 14.5px; color: var(--ink-soft); line-height: 1.6; }
.detail-form { margin: 8px 0 0; }
.detail-link {
  background: none; border: none; padding: 0; margin: 0;
  font: inherit; font-family: var(--font-mono); font-size: 12.5px;
  color: var(--accent); cursor: pointer; text-decoration: underline;
}
.detail-link:hover { color: var(--ink); }
.empty { color: var(--muted); font-size: 14.5px; padding: 20px 0; }
footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 11.5px; font-family: var(--font-mono); }

/* hub-page specific */
.hub-grid { display: grid; gap: 14px; }
.hub-card {
  display: block; text-decoration: none; color: inherit;
  background: var(--paper-raised); border: 1px solid var(--line);
  border-left: 3px solid var(--accent); border-radius: 8px;
  padding: 18px 20px;
}
.hub-card:hover { border-left-width: 5px; padding-left: 18px; }
.hub-card .name { font-weight: 700; font-size: 17px; margin-bottom: 4px; }
.hub-card .stat { font-family: var(--font-mono); font-size: 12.5px; color: var(--muted); }
.hub-card .stat.has-news { color: var(--accent); font-weight: 600; }
"""


def _page_shell(body_html, title, brand="MOPS Alert"):
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
{body_html}
</div>
</body>
</html>
"""


LIVE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"


def _detail_form_html(detail):
    """Reproduces MOPS's own "詳細資料" button as a plain auto-postable form
    (no JS needed) - added 2026-08-17 per Charles ("我需要的就是連接到這個按鈕
    之後的網頁"). MOPS renders that button's target via a JS-only re-POST of
    hidden fields (see mops_watch.py's _parse_detail docstring), so a normal
    <a href> can't reach it - this <form> reproduces the same POST a real
    click would send. `detail` is None for older accumulated rows saved
    before this field existed - degrade to no link rather than a broken one."""
    if not detail:
        return ""
    fields = {
        "TYPEK": detail["typek"],
        "step": "1",
        "skey": detail["skey"],
        "COMPANY_ID": detail["company_id"],
        "SPOKE_DATE": detail["spoke_date"],
        "SPOKE_TIME": detail["spoke_time"],
        "SEQ_NO": detail["seq_no"],
    }
    inputs = "".join(
        f'<input type="hidden" name="{_html.escape(k)}" value="{_html.escape(v)}">'
        for k, v in fields.items()
    )
    return (
        f'<form class="detail-form" method="post" action="{LIVE_URL}" target="_blank">'
        f"{inputs}"
        '<button type="submit" class="detail-link">查看原始公告 →</button>'
        "</form>"
    )


def render_html(output_path, person_label, title, date_str, count_label, disclosures,
                 back_href="../"):
    """Per-person page. disclosures: list of dicts with keys ticker, name,
    subject, announce_date, detail (detail may be None - see _detail_form_html)."""
    cards = []
    if disclosures:
        for d in disclosures:
            cards.append(
                '<div class="card">'
                f'<div class="co">{_html.escape(d["name"])}'
                f'<span class="code">{_html.escape(d["ticker"])}</span></div>'
                f'<div class="subject">{_html.escape(d["subject"])}</div>'
                f'{_detail_form_html(d.get("detail"))}'
                '</div>'
            )
        body_html = "\n".join(cards)
    else:
        body_html = '<div class="empty">今日監控清單內無公司發布重大訊息公告。</div>'

    body = f"""  <header>
    <div class="brand">MOPS Alert · {_html.escape(person_label)}</div>
    <div class="backlink"><a href="{_html.escape(back_href)}">← 回總覽</a></div>
    <h1>{_html.escape(title)}</h1>
    <div class="meta">{_html.escape(date_str)}</div>
  </header>
  <div class="count">{_html.escape(count_label)}</div>
  {body_html}
  <footer>資料來源：mopsov.twse.com.tw 即時重大訊息查詢・由 GitHub Actions 每日自動更新</footer>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(_page_shell(body, title, brand=f"MOPS Alert · {person_label}"))
    return output_path


def render_hub(output_path, date_str, people):
    """Landing page linking to each person's page.
    people: list of dicts with keys label, href, count."""
    cards = []
    for p in people:
        stat_class = "stat has-news" if p["count"] > 0 else "stat"
        stat_text = f"今日 {p['count']} 則" if p["count"] > 0 else "今日無公告"
        cards.append(
            f'<a class="hub-card" href="{_html.escape(p["href"])}">'
            f'<div class="name">{_html.escape(p["label"])}</div>'
            f'<div class="{stat_class}">{_html.escape(stat_text)}</div>'
            '</a>'
        )

    body = f"""  <header>
    <div class="brand">MOPS Alert</div>
    <h1>重大訊息公告監控</h1>
    <div class="meta">{_html.escape(date_str)}</div>
  </header>
  <div class="hub-grid">
    {"".join(cards)}
  </div>
  <footer>資料來源：mopsov.twse.com.tw 即時重大訊息查詢・由 GitHub Actions 每日自動更新</footer>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(_page_shell(body, "MOPS Alert 總覽"))
    return output_path
