# -*- coding: utf-8 -*-
"""
ASTRODDS 118 - Over/Under Paper Test Ledger

Purpose:
- Create a separate O/U paper-test ledger from the latest O/U probability model.
- This does NOT affect verified Telegram A+ record.
- O/U picks can be tracked separately to test profitability.

Safe:
- No Telegram send
- No official public win-rate change
- No betting automation
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import html
import re

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

OU_MODEL = ROOT / ".astrodds" / "ASTRODDS-over-under-probability-edge-model-latest.json"
LEDGER = ROOT / ".astrodds" / "ou-paper-test-ledger.json"
PUBLIC_JSON = ROOT / "public" / "astrodds-ou-paper-test-results.json"
PUBLIC_HTML = ROOT / "public" / "astrodds-ou-paper-test-results.html"
REPORT = BASE / "reports" / "118_ou_paper_test_ledger_report.txt"

ET = ZoneInfo("America/Toronto")

INCLUDED_CATEGORIES = ["O/U_PICK", "O/U_LEAN"]

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def safe_slug(value):
    raw = str(value or "").lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return raw[:80]

def candidate_id(c):
    return "|".join([
        str(c.get("date") or ""),
        safe_slug(c.get("game")),
        safe_slug(c.get("pick")),
        str(c.get("line") or ""),
        str(c.get("category") or ""),
    ])

def money(v):
    try:
        n = float(v or 0)
        sign = "+" if n >= 0 else "-"
        return f"{sign}${abs(n):.2f}"
    except Exception:
        return "-"

def pct(v):
    try:
        return f"{float(v) * 100:.2f}%"
    except Exception:
        return "-"

def main():
    generated = datetime.now(ET).isoformat()

    model = read_json(OU_MODEL, {"candidates": []})
    ledger = read_json(LEDGER, {
        "createdAt": generated,
        "rules": {
            "purpose": "Separate Over/Under paper test ledger.",
            "doesNotAffect": "Official Telegram A+ verified win rate.",
            "included": INCLUDED_CATEGORIES,
            "excluded": ["O/U_WATCH", "Moneyline", "Telegram official record"]
        },
        "signals": []
    })

    ledger.setdefault("signals", [])
    existing = {s.get("signalId") for s in ledger["signals"]}

    added = 0
    skipped = 0

    for c in model.get("candidates", []):
        if c.get("category") not in INCLUDED_CATEGORIES:
            continue

        sid = candidate_id(c)
        if sid in existing:
            skipped += 1
            continue

        ledger["signals"].append({
            "signalId": sid,
            "addedAt": generated,
            "date": c.get("date"),
            "game": c.get("game"),
            "pick": c.get("pick"),
            "marketType": "over_under",
            "category": c.get("category"),
            "status": "PENDING",
            "result": "PENDING",
            "paperOnly": True,
            "telegramOfficial": False,
            "line": c.get("line"),
            "priceAmerican": c.get("priceAmerican"),
            "modelProbability": c.get("modelProbability"),
            "marketProbability": c.get("marketProbability"),
            "probabilityEdge": c.get("probabilityEdge"),
            "projectedTotalRuns": c.get("projectedTotalRuns"),
            "edgeRuns": c.get("edgeRuns"),
            "stake": c.get("stake"),
            "reason": c.get("reason"),
        })
        added += 1

    ledger["updatedAt"] = generated

    signals = ledger["signals"]
    wins = [s for s in signals if s.get("result") == "WIN"]
    losses = [s for s in signals if s.get("result") == "LOSS"]
    pushes = [s for s in signals if s.get("result") == "PUSH"]
    pending = [s for s in signals if s.get("result") == "PENDING"]
    graded = len(wins) + len(losses)
    win_rate = len(wins) / graded if graded else 0.0

    ledger["summary"] = {
        "ouPaperSignals": len(signals),
        "wins": len(wins),
        "losses": len(losses),
        "pushes": len(pushes),
        "pending": len(pending),
        "graded": graded,
        "winRate": round(win_rate, 4),
        "winRateLabel": f"{win_rate:.0%}" if graded else "N/A",
    }

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    public = {
        "generatedAt": generated,
        "title": "ASTRODDS Over/Under Paper Test Results",
        "rules": ledger["rules"],
        "summary": ledger["summary"],
        "signals": sorted(signals, key=lambda x: str(x.get("date") or ""), reverse=True),
    }

    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = []
    for s in public["signals"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(s.get('date') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('game') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('pick') or '-'))}</td>"
            f"<td>{html.escape(str(s.get('category') or '-'))}</td>"
            f"<td>{html.escape(pct(s.get('modelProbability')))}</td>"
            f"<td>{html.escape(pct(s.get('marketProbability')))}</td>"
            f"<td>{html.escape(pct(s.get('probabilityEdge')))}</td>"
            f"<td>{html.escape(str(s.get('edgeRuns') or '-'))}</td>"
            f"<td class='result {html.escape(str(s.get('result') or '').lower())}'>{html.escape(str(s.get('result') or '-'))}</td>"
            "</tr>"
        )

    html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ASTRODDS O/U Paper Test</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; color: #101828; background: #f8fafc; }}
.card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 24px; max-width: 1200px; box-shadow: 0 8px 24px rgba(16,24,40,.06); }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 20px 0; }}
.metric {{ background: #f1f5f9; border-radius: 12px; padding: 16px; }}
.metric .label {{ color: #667085; font-size: 13px; }}
.metric .value {{ font-size: 28px; font-weight: 800; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
th,td {{ text-align: left; padding: 11px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
th {{ color: #667085; text-transform: uppercase; font-size: 12px; }}
.result.win {{ color:#16a34a; font-weight:800; }}
.result.loss {{ color:#dc2626; font-weight:800; }}
.result.push {{ color:#f59e0b; font-weight:800; }}
.result.pending {{ color:#2563eb; font-weight:800; }}
.note {{ color:#667085; margin-top: 16px; font-size: 13px; }}
</style>
</head>
<body>
<div class="card">
<h1>ASTRODDS Over/Under Paper Test</h1>
<div class="note">Separate test ledger. This does not affect official Telegram A+ win rate.</div>
<div class="summary">
  <div class="metric"><div class="label">O/U Test Signals</div><div class="value">{len(signals)}</div></div>
  <div class="metric"><div class="label">Record</div><div class="value">{len(wins)}-{len(losses)}</div></div>
  <div class="metric"><div class="label">Win Rate</div><div class="value">{ledger['summary']['winRateLabel']}</div></div>
  <div class="metric"><div class="label">Pending</div><div class="value">{len(pending)}</div></div>
</div>
<table>
<thead>
<tr>
<th>Date</th><th>Game</th><th>Pick</th><th>Type</th><th>Model</th><th>Market</th><th>Edge</th><th>EdgeRuns</th><th>Result</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
<div class="note">Generated: {html.escape(generated)}</div>
</div>
</body>
</html>"""
    PUBLIC_HTML.write_text(html_doc, encoding="utf-8")

    lines = [
        "ASTRODDS 118 O/U PAPER TEST LEDGER",
        "=" * 58,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Separate O/U paper-test ledger.",
        "- Does not affect official Telegram A+ record.",
        "- Includes O/U_PICK and O/U_LEAN only.",
        "- Excludes O/U_WATCH.",
        "",
        f"Added: {added}",
        f"Skipped existing: {skipped}",
        "",
        "Summary:",
        f"- O/U paper signals: {len(signals)}",
        f"- Record: {len(wins)}-{len(losses)}",
        f"- Win rate: {ledger['summary']['winRateLabel']}",
        f"- Pushes: {len(pushes)}",
        f"- Pending: {len(pending)}",
        "",
        f"Ledger: {LEDGER}",
        f"Public JSON: {PUBLIC_JSON}",
        f"Public HTML: {PUBLIC_HTML}",
        "",
        "Signals:",
    ]

    for s in public["signals"]:
        lines.append(
            f"- {s.get('date')} | {s.get('game')} | {s.get('pick')} | "
            f"{s.get('category')} | Edge={pct(s.get('probabilityEdge'))} | Result={s.get('result')}"
        )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
