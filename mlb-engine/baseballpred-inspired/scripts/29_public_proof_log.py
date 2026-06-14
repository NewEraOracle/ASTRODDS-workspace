from pathlib import Path
import json
from datetime import datetime
import html

BASE = Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parents[1]

LEDGER = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
CLV = WORKSPACE / ".astrodds" / "ASTRODDS-clv-line-movement-latest.json"

OUT_JSON = WORKSPACE / "public" / "astrodds-proof-log.json"
OUT_HTML = WORKSPACE / "public" / "astrodds-proof-log.html"
REPORT = BASE / "reports" / "29_public_proof_log_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def pct(x):
    v = fnum(x)
    if v is None:
        return "-"
    if abs(v) <= 1:
        return f"{round(v * 100, 2)}%"
    return f"{round(v, 2)}%"

def units(x):
    v = fnum(x)
    if v is None:
        return "0.000u"
    return f"{round(v, 3)}u"

def status_badge(result):
    r = str(result or "pending").lower()
    if r == "win":
        return "WIN"
    if r == "loss":
        return "LOSS"
    if r == "push":
        return "PUSH"
    if r == "void":
        return "VOID"
    return "PENDING"

def safe(x):
    return html.escape(str(x if x is not None else ""))

def main():
    ledger = read_json(LEDGER, [])
    clv_rows = read_json(CLV, [])

    clv_by_key = {}
    for c in clv_rows:
        key = f"{c.get('gameId')}|{c.get('pick')}"
        clv_by_key[key] = c

    proof_rows = []

    for r in ledger:
        key = f"{r.get('gameId')}|{r.get('pick')}"
        clv = clv_by_key.get(key, {})

        proof_rows.append({
            "date": r.get("date"),
            "game": r.get("game"),
            "pick": r.get("pick"),
            "decision": r.get("finalEngineDecision"),
            "grade": r.get("finalGrade"),
            "marketProbability": r.get("marketProbability"),
            "calibratedProbability": r.get("calibratedProbabilityV2"),
            "calibratedEdgePct": r.get("calibratedEdgePct"),
            "clvStatus": clv.get("clvStatus", "unknown"),
            "marketMovementPctPoints": clv.get("marketMovementPctPoints", ""),
            "result": r.get("result", "pending"),
            "winner": r.get("winner", ""),
            "score": f"{r.get('awayRuns', '-')}-{r.get('homeRuns', '-')}",
            "paperProfitUnits": r.get("paperProfitUnits", 0),
            "loggedAt": r.get("ledgerAddedAt"),
            "resolvedAt": r.get("resolvedAt", ""),
            "paperOnly": True,
        })

    proof_rows.sort(key=lambda x: str(x.get("date") or ""), reverse=True)

    summary = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "paper_only",
        "totalSignals": len(proof_rows),
        "wins": sum(1 for r in proof_rows if r.get("result") == "win"),
        "losses": sum(1 for r in proof_rows if r.get("result") == "loss"),
        "pending": sum(1 for r in proof_rows if r.get("result") == "pending"),
        "engineBuy": sum(1 for r in proof_rows if r.get("decision") == "ENGINE_BUY"),
        "manualReview": sum(1 for r in proof_rows if r.get("decision") == "MANUAL_REVIEW"),
        "watch": sum(1 for r in proof_rows if r.get("decision") == "WATCH"),
        "paperProfitUnits": round(sum(fnum(r.get("paperProfitUnits")) or 0 for r in proof_rows), 3),
        "note": "ASTRODDS proof log is paper/manual only. No real-money automation.",
    }

    public_data = {
        "summary": summary,
        "rows": proof_rows,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(public_data, indent=2), encoding="utf-8")

    rows_html = []

    for r in proof_rows:
        result = status_badge(r.get("result"))
        css = result.lower()

        rows_html.append(f"""
        <tr>
          <td>{safe(r.get('date'))}</td>
          <td>{safe(r.get('game'))}</td>
          <td><strong>{safe(r.get('pick'))}</strong></td>
          <td>{safe(r.get('decision'))}</td>
          <td>{safe(r.get('grade'))}</td>
          <td>{pct(r.get('marketProbability'))}</td>
          <td>{pct(r.get('calibratedProbability'))}</td>
          <td>{safe(r.get('calibratedEdgePct'))}%</td>
          <td>{safe(r.get('clvStatus'))}</td>
          <td><span class="badge {css}">{result}</span></td>
          <td>{safe(r.get('winner'))}</td>
          <td>{safe(r.get('score'))}</td>
          <td>{units(r.get('paperProfitUnits'))}</td>
        </tr>
        """)

    page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ASTRODDS Proof Log</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{
      margin: 0;
      background: #07070a;
      color: #f4f4f5;
      font-family: Arial, Helvetica, sans-serif;
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      letter-spacing: -0.03em;
    }}
    .sub {{
      color: #a1a1aa;
      margin-bottom: 24px;
      line-height: 1.5;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 22px 0 28px;
    }}
    .card {{
      background: #111118;
      border: 1px solid #27272a;
      border-radius: 14px;
      padding: 16px;
    }}
    .label {{
      color: #a1a1aa;
      font-size: 12px;
      text-transform: uppercase;
    }}
    .value {{
      font-size: 24px;
      font-weight: 800;
      margin-top: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #101016;
      border: 1px solid #27272a;
      border-radius: 14px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid #27272a;
      font-size: 13px;
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      background: #18181f;
      color: #d4d4d8;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .badge {{
      padding: 5px 8px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 11px;
    }}
    .win {{ background: #064e3b; color: #a7f3d0; }}
    .loss {{ background: #7f1d1d; color: #fecaca; }}
    .pending {{ background: #3f3f46; color: #f4f4f5; }}
    .push, .void {{ background: #78350f; color: #fde68a; }}
    .note {{
      margin-top: 18px;
      color: #a1a1aa;
      font-size: 12px;
    }}
    @media (max-width: 900px) {{
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>ASTRODDS Proof Log</h1>
    <div class="sub">
      Public paper-trading proof log generated from ASTRODDS Engine V2.
      Signals are logged from the final engine decision layer and resolved after games finish.
      No real-money automation.
    </div>

    <div class="cards">
      <div class="card"><div class="label">Signals</div><div class="value">{summary['totalSignals']}</div></div>
      <div class="card"><div class="label">Wins</div><div class="value">{summary['wins']}</div></div>
      <div class="card"><div class="label">Losses</div><div class="value">{summary['losses']}</div></div>
      <div class="card"><div class="label">Pending</div><div class="value">{summary['pending']}</div></div>
      <div class="card"><div class="label">Paper Units</div><div class="value">{summary['paperProfitUnits']}u</div></div>
    </div>

    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Game</th>
          <th>Pick</th>
          <th>Decision</th>
          <th>Grade</th>
          <th>Market</th>
          <th>Calibrated</th>
          <th>Edge</th>
          <th>CLV</th>
          <th>Result</th>
          <th>Winner</th>
          <th>Score</th>
          <th>Units</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>

    <div class="note">
      Generated at {summary['generatedAt']}. This page is for research and paper tracking only.
    </div>
  </div>
</body>
</html>
"""

    OUT_HTML.write_text(page, encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 29 PUBLIC PROOF LOG REPORT")
    lines.append("=" * 44)
    lines.append(f"Generated: {summary['generatedAt']}")
    lines.append("")
    lines.append(f"Signals: {summary['totalSignals']}")
    lines.append(f"Wins: {summary['wins']}")
    lines.append(f"Losses: {summary['losses']}")
    lines.append(f"Pending: {summary['pending']}")
    lines.append(f"Paper profit units: {summary['paperProfitUnits']}u")
    lines.append("")
    lines.append("Proof log rows:")
    for r in proof_rows:
        lines.append(
            f"- {r.get('date')} | {r.get('game')} | Pick: {r.get('pick')} | "
            f"Decision: {r.get('decision')} | Grade: {r.get('grade')} | "
            f"Result: {r.get('result')} | Units: {r.get('paperProfitUnits')}"
        )
    lines.append("")
    lines.append(f"HTML: {OUT_HTML}")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
