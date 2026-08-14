"""
HTML renderer for the mops-alert cloud page (adapted 2026-08-14 from
MOPSAlertRobot's local version at ~/Projects/MOPSAlertRobot/html_report.py).
Same look, no external assets, light/dark via prefers-color-scheme - the
whole point of a static single-file page hosted on GitHub Pages.
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
.empty { color: var(--muted); font-size: 14.5px; padding: 20px 0; }
footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 11.5px; font-family: var(--font-mono); }
"""


def render_html(output_path, title, date_str, count_label, disclosures):
    """disclosures: list of dicts with keys ticker, name, subject, announce_date."""
    cards = []
    if disclosures:
        for d in disclosures:
            cards.append(
                '<div class="card">'
                f'<div class="co">{_html.escape(d["name"])}'
                f'<span class="code">{_html.escape(d["ticker"])}</span></div>'
                f'<div class="subject">{_html.escape(d["subject"])}</div>'
                '</div>'
            )
        body_html = "\n".join(cards)
    else:
        body_html = '<div class="empty">今日監控清單內無公司發布重大訊息公告。</div>'

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <header>
    <div class="brand">MOPS Alert</div>
    <h1>{_html.escape(title)}</h1>
    <div class="meta">{_html.escape(date_str)}</div>
  </header>
  <div class="count">{_html.escape(count_label)}</div>
  {body_html}
  <footer>資料來源：mopsov.twse.com.tw 即時重大訊息查詢・由 GitHub Actions 每日自動更新</footer>
</div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path
