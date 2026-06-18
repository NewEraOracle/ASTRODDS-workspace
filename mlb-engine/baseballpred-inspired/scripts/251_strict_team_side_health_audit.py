from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
BOARD = ASTRO / "ASTRODDS-source-first-strict-team-side-board-latest.json"
ACTION = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "251_strict_team_side_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    b = load(BOARD)
    a = load(ACTION)
    rows = b.get("moneylineBoard", [])
    dup_same = []
    by_game = {}
    for r in rows:
        by_game.setdefault(r.get("game",""), []).append(r)
    for game, group in by_game.items():
        if len(group) == 2:
            x,y = group
            if x.get("price") is not None and y.get("price") is not None and x.get("price") == y.get("price"):
                dup_same.append(f"{game} same price {x.get('price')}")
            if x.get("modelProbability") is not None and y.get("modelProbability") is not None and x.get("modelProbability") == y.get("modelProbability"):
                dup_same.append(f"{game} same model {x.get('modelProbability')}")

    if dup_same:
        overall = "CHECK_DUPLICATE_SIDE_VALUES"
    elif b.get("rowsWithPrice",0) == 0:
        overall = "PRICE_MATCHER_TOO_STRICT"
    else:
        overall = "OK_SAFE"

    lines = [
        "ASTRODDS 251 STRICT TEAM-SIDE HEALTH AUDIT",
        "="*72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Official games: {b.get('officialGames')}",
        f"Rows: {b.get('rows')}",
        f"Rows with price: {b.get('rowsWithPrice')}",
        f"Rows with model: {b.get('rowsWithModel')}",
        f"Rows with edge: {b.get('rowsWithEdge')}",
        f"Duplicate side issues: {len(dup_same)}",
        f"Actionable rows: {a.get('actionableRows','unknown')}",
        "",
        "Duplicate side issues:",
    ]
    if dup_same:
        for d in dup_same:
            lines.append(f"- {d}")
    else:
        lines.append("- none")

    lines += ["", "Actionable:"]
    acts = a.get("actionableMoneyline", []) or []
    if acts:
        for r in acts:
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct')} | status={r.get('liveMlbStatus')}")
    else:
        lines.append("- none")

    lines += ["", "Rule: safe board prefers missing values over assigning same side value to both teams."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
