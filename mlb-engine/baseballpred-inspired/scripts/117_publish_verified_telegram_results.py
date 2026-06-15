# -*- coding: utf-8 -*-
"""
ASTRODDS 117 - Publish Verified Telegram Results

Purpose:
- Build the public proof JSON/HTML from .astrodds/telegram-verified-signal-ledger.json
- Only verified Telegram A+/official signals are shown.
- Paper picks, watchlist, model-only, non-Telegram leans are excluded.

Safe:
- Does not send Telegram
- Does not create picks
- Does not modify engine decisions
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import html

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LEDGER = ROOT / ".astrodds" / "telegram-verified-signal-ledger.json"
PUBLIC_JSON = ROOT / "public" / "astrodds-verified-telegram-results.json"
PUBLIC_HTML = ROOT / "public" / "astrodds-verified-telegram-results.html"
REPORT = BASE / "reports" / "117_publish_verified_telegram_results_report.txt"

ET = ZoneInfo("America/Toronto")

def read_json(path):
    if not path.exists():
        return {"signals": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"signals": []}

def is_countable_signal(s):
    if not s.get("telegramSent"):
        return False
    if str(s.get("grade") or "").upper() not in ["A+", "OFFICIAL", "A_PLUS"]:
        return False
    if str(s.get("result") or "").upper() not in ["WIN", "LOSS", "PUSH", "PENDING"]:
        return False
    return True

def money(v):
    try:
        n = float(v or 0)
        sign = "+" if n >= 0 else "-"
        return f"{sign}${abs(n):.2f}"
    except Exception:
        return "-"

def main():
    generated = datetime.now(ET).isoformat()
    ledger = read_json(LEDGER)

    signals = [s for s in ledger.get("signals", []) if is_countable_signal(s)]

    # Sort newest first for display.
    signals.sort(key=lambda x: str(x.get("signalDate") or ""), reverse=True)

    wins = [s for s in signals if str(s.get("result")).upper() == "WIN"]
    losses = [s for s in signals if str(s.get("result")).upper() == "LOSS"]
    pushes = [s for s in signals if str(s.get("result")).upper() == "PUSH"]
    pending = [s for s in signals if str(s.get("result")).upper() == "PENDING"]

    graded = len(wins) + len(losses)
    win_rate = (len(wins) / graded) if graded else 0.0
    total_profit = sum(float(s.get("profit") or 0) for s in wins)

    output = {
        "generatedAt": generated,
        "title": "ASTRODDS Verified Telegram Results",
        "rules": {
            "included": "Only verified Telegram A+/official signals.",
            "excluded": ["paper picks", "watchlist", "model-only", "non-Telegram value/action leans"],
            "note": "Manual seed entries are marked manualVerified=true."
        },
        "summary": {
            "record": f"{len(wins)}-{len(losses)}",
            "wins": len(wins),
            "losses": len(losses),
            "pushes": len(pushes),
            "pending": len(pending),
            "graded": graded,
            "winRate": round(win_rate, 4),
            "winRateLabel": f"{win_rate:.0%}",
            "totalProfitTracked": round(total_profit, 2),
        },
        "signals": signals,
    }

    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = []
    for s in signals:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(s.get('signalDate') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('market') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('pick') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('grade') or '-'))}</td>"
            f"<td class='result {html.escape(str(s.get('result') or '').lower())}'>{html.escape(str(s.get('result') or '-'))}</td>"
            f"<td>{html.escape(money(s.get('profit')))}</td>"
            f"<td>{'Manual verified' if s.get('manualVerified') else 'Auto tracked'}</td>"
            "</tr>"
        )

    html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ASTRODDS Verified Telegram Results</title>
<style>
body {{
  font-family: Arial, sans-serif;
  margin: 32px;
  color: #101828;
  background: #f8fafc;
}}
.card {{
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 24px;
  max-width: 1100px;
  box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
}}
h1 {{ margin: 0 0 8px; }}
.summary {{
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin: 20px 0;
}}
.metric {{
  background: #f1f5f9;
  border-radius: 12px;
  padding: 16px;
}}
.metric .label {{
  color: #667085;
  font-size: 13px;
}}
.metric .value {{
  font-size: 28px;
  font-weight: 800;
  margin-top: 4px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 18px;
}}
th, td {{
  text-align: left;
  padding: 12px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
}}
th {{
  color: #667085;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: .04em;
}}
.result.win {{ color: #16a34a; font-weight: 800; }}
.result.loss {{ color: #dc2626; font-weight: 800; }}
.result.push {{ color: #f59e0b; font-weight: 800; }}
.note {{
  color: #667085;
  margin-top: 16px;
  font-size: 13px;
}}
</style>
</head>
<body>
<div class="card">
<h1>ASTRODDS Verified Telegram Results</h1>
<div class="note">Only verified Telegram A+ / official signals are counted. Paper picks, watchlist, and model-only leans are excluded.</div>

<div class="summary">
  <div class="metric"><div class="label">Record</div><div class="value">{output['summary']['record']}</div></div>
  <div class="metric"><div class="label">Win Rate</div><div class="value">{output['summary']['winRateLabel']}</div></div>
  <div class="metric"><div class="label">Tracked Profit</div><div class="value">{money(total_profit)}</div></div>
  <div class="metric"><div class="label">Verified Signals</div><div class="value">{len(signals)}</div></div>
</div>

<table>
<thead>
<tr>
<th>Date</th>
<th>Market</th>
<th>Pick</th>
<th>Grade</th>
<th>Result</th>
<th>Profit</th>
<th>Verification</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>

<div class="note">Generated: {html.escape(generated)}</div>
</div>
</body>
</html>
"""
    PUBLIC_HTML.write_text(html_doc, encoding="utf-8")

    lines = [
        "ASTRODDS 117 PUBLISH VERIFIED TELEGRAM RESULTS",
        "=" * 64,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Only verified Telegram A+/official signals are included.",
        "- Paper picks, watchlist, model-only, and non-Telegram leans are excluded.",
        "",
        "Summary:",
        f"- Record: {output['summary']['record']}",
        f"- Win rate: {output['summary']['winRateLabel']}",
        f"- Wins: {len(wins)}",
        f"- Losses: {len(losses)}",
        f"- Pushes: {len(pushes)}",
        f"- Pending: {len(pending)}",
        f"- Verified signals: {len(signals)}",
        f"- Total profit tracked: {money(total_profit)}",
        "",
        f"Public JSON: {PUBLIC_JSON}",
        f"Public HTML: {PUBLIC_HTML}",
        "",
        "Shown signals:",
    ]

    for s in signals:
        lines.append(f"- {s.get('signalDate')} | {s.get('market')} | Pick={s.get('pick')} | Result={s.get('result')} | Profit={money(s.get('profit'))}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
