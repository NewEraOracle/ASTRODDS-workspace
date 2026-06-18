from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
SRC_JSON = ASTRO / "ASTRODDS-source-first-moneyline-board-latest.json"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "248_source_first_moneyline_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    src = load(SRC_JSON)
    act = load(ACTION_JSON)
    rows = src.get("moneylineBoard", [])
    official_games = src.get("officialGames", 0)
    rows_with_price = src.get("rowsWithPrice", 0)
    rows_with_model = src.get("rowsWithModel", 0)
    rows_with_edge = src.get("rowsWithEdge", 0)
    expected_rows = int(official_games) * 2 if official_games else 0

    if rows_with_price == expected_rows and rows_with_edge == expected_rows:
        overall = "OK_FULL_SLATE"
    elif rows_with_price == expected_rows:
        overall = "PRICE_OK_MODEL_INCOMPLETE"
    else:
        overall = "PRICE_INCOMPLETE"

    lines = [
        "ASTRODDS 248 SOURCE-FIRST MONEYLINE HEALTH AUDIT",
        "=" * 78,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Official games: {official_games}",
        f"Expected rows: {expected_rows}",
        f"Rows: {len(rows)}",
        f"Rows with price: {rows_with_price}",
        f"Rows with model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Actionable rows: {act.get('actionableRows','unknown')}",
        "",
        "Rows missing price:",
    ]

    missing_price = [r for r in rows if r.get("price") is None]
    if missing_price:
        for r in missing_price:
            lines.append(f"- {r.get('pick')} | {r.get('game')} | status={r.get('liveMlbStatus')}")
    else:
        lines.append("- none")

    lines += ["", "Actionable:"]
    actions = act.get("actionableMoneyline", []) or []
    if actions:
        for r in actions:
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct')} | status={r.get('liveMlbStatus')}")
    else:
        lines.append("- none")

    lines += ["", "Rule: source-first board must start from official schedule, never stale odds games."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
