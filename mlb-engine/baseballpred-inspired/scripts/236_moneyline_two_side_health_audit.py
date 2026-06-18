from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
REPORT = REPORTS / "236_moneyline_two_side_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fnum(v, default=None):
    if v is None:
        return default
    try:
        s = str(v).replace(",", ".").replace("%","").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def main():
    action = load(ACTION_JSON)
    board = load(BOARD_JSON)
    rows = board.get("moneylineBoard", [])
    with_price = [r for r in rows if fnum(r.get("price"), None) is not None]
    with_model = [r for r in rows if fnum(r.get("modelProbability"), None) is not None]
    with_edge = [r for r in rows if fnum(r.get("currentEdgePct", r.get("edgePct")), None) is not None]
    filled = [r for r in rows if r.get("modelProbabilitySource") == "two_side_inverse_from_opponent"]
    direct = [r for r in rows if r.get("modelProbabilitySource") == "direct_model_candidate_or_existing"]
    actions = action.get("actionableMoneyline", [])
    bad = [r for r in actions if fnum(r.get("price"),None) is None or fnum(r.get("modelProbability"),None) is None or fnum(r.get("currentEdgePct"),None) is None]
    ok = bool(rows) and len(with_price) == len(rows) and len(with_model) >= 20 and not bad

    lines = [
        "ASTRODDS 236 MONEYLINE TWO-SIDE HEALTH AUDIT",
        "="*72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {'OK' if ok else 'CHECK'}",
        "",
        f"Board rows: {len(rows)}",
        f"Rows with price: {len(with_price)}",
        f"Rows with modelProbability: {len(with_model)}",
        f"Rows with edge: {len(with_edge)}",
        f"Direct model rows: {len(direct)}",
        f"Two-side filled rows: {len(filled)}",
        f"Actionable rows: {action.get('actionableRows','unknown')}",
        f"Bad actionable rows: {len(bad)}",
        "",
        "Actionable:",
    ]
    if actions:
        for r in actions:
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct')} | model={r.get('modelProbability')} | price={r.get('price')} | status={r.get('liveMlbStatus','')}")
    else:
        lines.append("- none")
    lines += ["", "Rule: board should have price/model/edge coverage for both sides when one side model exists."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
