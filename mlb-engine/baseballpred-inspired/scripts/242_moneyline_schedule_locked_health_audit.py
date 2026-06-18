from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

COVERAGE_JSON = ASTRO / "ASTRODDS-moneyline-official-schedule-price-coverage-latest.json"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "242_moneyline_schedule_locked_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    cov = load(COVERAGE_JSON)
    act = load(ACTION_JSON)

    decision = cov.get("decision", "UNKNOWN")
    missing = int(cov.get("missingOfficialGamesCount", 0) or 0)
    stale = int(cov.get("rejectedStaleRows", 0) or 0)
    actionable = int(act.get("actionableRows", 0) or 0)

    if decision == "OK":
        overall = "OK"
    elif missing > 0:
        overall = "NOT_FULL_SLATE_READY"
    else:
        overall = "WARNING"

    lines = [
        "ASTRODDS 242 MONEYLINE SCHEDULE LOCKED HEALTH AUDIT",
        "=" * 78,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Coverage decision: {decision}",
        f"Missing official games from price board: {missing}",
        f"Rejected stale/nonexistent rows: {stale}",
        f"Actionable rows after schedule lock: {actionable}",
        "",
        "Actionable rows:",
    ]

    acts = act.get("actionableMoneyline", []) or []
    if acts:
        for r in acts:
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct')} | status={r.get('liveMlbStatus')} | source={r.get('statusSourceUsed')}")
    else:
        lines.append("- none")

    if missing > 0:
        lines += ["", "Missing official games:"]
        for g in cov.get("missingOfficialGames", []) or []:
            lines.append(f"- {g.get('officialGame')} | {g.get('liveMlbStatus')} | {g.get('gameDate')} | gamePk={g.get('gamePk')}")

    lines += [
        "",
        "Rule:",
        "- If Overall is NOT_FULL_SLATE_READY, the issue is odds/price coverage, not the model guard.",
        "- Fix the odds collector/price source before calling it BaseballPred-style full slate.",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
