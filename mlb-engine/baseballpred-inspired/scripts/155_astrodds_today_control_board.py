from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"
OU_JSON = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
OU_V2_JSON = ASTRO / "ASTRODDS-ou-v2-strict-paper-score-latest.json"
ML_CSV = ASTRO / "ASTRODDS-clean-moneyline-record.csv"
OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
AB_CSV = ASTRO / "ASTRODDS-ou-v1-v2-ab-test-record.csv"
REPORT = REPORTS / "155_astrodds_today_control_board_report.txt"
OUT_HTML = ASTRO / "astrodds-today-control-board.html"
OUT_JSON = ASTRO / "ASTRODDS-today-control-board-latest.json"

ET = ZoneInfo("America/New_York")

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def today():
    return datetime.now(ET).date().isoformat()

def esc(x):
    return str(x or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    date = today()
    board = load_json(BOARD_JSON, {})
    ou = load_json(OU_JSON, {})
    ou_v2 = load_json(OU_V2_JSON, {})

    ml_rows = read_csv(ML_CSV)
    ou_rows = read_csv(OU_CSV)
    ab_rows = read_csv(AB_CSV)

    a_picks = board.get("aPicks", []) if isinstance(board, dict) else []
    ou_candidates = ou.get("candidates", []) if isinstance(ou, dict) else []
    v2_candidates = ou_v2.get("candidates", []) if isinstance(ou_v2, dict) else []

    today_ml_pending = [r for r in ml_rows if r.get("date") == date and str(r.get("result","")).lower() == "pending"]
    today_ou_pending = [r for r in ou_rows if r.get("date") == date and str(r.get("result","")).lower() == "pending"]

    out = {
        "generatedAt": datetime.now(ET).isoformat(),
        "date": date,
        "moneylineAPicks": a_picks,
        "ouAPlusLive": [r for r in ou_candidates if str(r.get("category","")).upper() == "O/U_PICK" and float(r.get("edgeRuns",0) or 0) >= 1.75],
        "v2PaperAPlus": [r for r in v2_candidates if r.get("strictV2Grade") == "V2_A_PLUS_PAPER"],
        "v2Review": [r for r in v2_candidates if r.get("strictV2Grade") == "V2_REVIEW"],
        "pending": {
            "moneyline": today_ml_pending,
            "ou": today_ou_pending,
        },
        "nextScans": ["14:00 ET", "17:10 ET", "02:30 ET results"],
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS TODAY CONTROL BOARD",
        "=" * 48,
        f"Generated ET: {out['generatedAt']}",
        f"Date: {date}",
        "",
        f"Moneyline A/A+ candidates: {len(a_picks)}",
        f"O/U live A+ candidates: {len(out['ouAPlusLive'])}",
        f"O/U V2 paper A+ candidates: {len(out['v2PaperAPlus'])}",
        f"O/U V2 review candidates: {len(out['v2Review'])}",
        f"Pending Moneyline today: {len(today_ml_pending)}",
        f"Pending O/U today: {len(today_ou_pending)}",
        "",
        "Moneyline:",
    ]
    for r in a_picks[:10]:
        lines.append(f"- {r.get('pick')} | {r.get('game')} | model={r.get('model')} edge={r.get('edge')}")

    lines += ["", "O/U Live A+:"]
    for r in out["ouAPlusLive"]:
        lines.append(f"- {r.get('pick')} | {r.get('game')} | line={r.get('line')} projected={r.get('projectedTotalRuns')} edge={r.get('edgeRuns')}")

    lines += ["", "O/U V2 Paper A+:"]
    for r in out["v2PaperAPlus"]:
        lines.append(f"- {r.get('pick')} | {r.get('game')} | strictScore={r.get('strictV2Score')} edge={r.get('edgeRuns')}")

    html_rows = ""
    for section, rows in [("Moneyline", a_picks[:10]), ("O/U Live A+", out["ouAPlusLive"]), ("O/U V2 Paper A+", out["v2PaperAPlus"]), ("O/U V2 Review", out["v2Review"])]:
        html_rows += f"<h2>{esc(section)}</h2><table><tr><th>Pick</th><th>Game</th><th>Info</th></tr>"
        for r in rows:
            info = f"edge={r.get('edge', r.get('edgeRuns',''))} score={r.get('strictV2Score','')}"
            html_rows += f"<tr><td>{esc(r.get('pick'))}</td><td>{esc(r.get('game'))}</td><td>{esc(info)}</td></tr>"
        html_rows += "</table>"

    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>ASTRODDS Today Board</title>
<style>body{{font-family:Arial;background:#f7fafc;padding:24px}}.card{{background:white;border-radius:16px;padding:24px;max-width:1100px;margin:auto;box-shadow:0 8px 22px #0001}}table{{width:100%;border-collapse:collapse;margin-bottom:18px}}td,th{{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.box{{background:#f1f5f9;padding:16px;border-radius:12px}}.v{{font-size:28px;font-weight:800}}</style></head>
<body><div class="card"><h1>ASTRODDS Today Control Board</h1><p>{esc(out['generatedAt'])}</p>
<div class="grid">
<div class="box"><div>Moneyline</div><div class="v">{len(a_picks)}</div></div>
<div class="box"><div>O/U Live A+</div><div class="v">{len(out['ouAPlusLive'])}</div></div>
<div class="box"><div>V2 Paper A+</div><div class="v">{len(out['v2PaperAPlus'])}</div></div>
<div class="box"><div>Pending</div><div class="v">{len(today_ml_pending)+len(today_ou_pending)}</div></div>
</div>{html_rows}<p>Next scans: 14:00 ET, 17:10 ET, 02:30 ET results. Paper/manual only.</p></div></body></html>"""
    OUT_HTML.write_text(html, encoding="utf-8")

    lines += ["", f"HTML: {OUT_HTML}", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
