from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FILTER_JSON = ASTRO / "ASTRODDS-moneyline-authoritative-schedule-filter-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-official-schedule-price-coverage-latest.json"
REPORT = REPORTS / "240_official_schedule_price_coverage_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    data = load(FILTER_JSON)
    missing = data.get("missingOfficialGames", []) or []
    rejected = data.get("rejectedRowsPreview", []) or []
    official_games = int(data.get("officialGames", 0) or 0)
    kept_rows = int(data.get("keptRows", 0) or 0)
    rejected_rows = int(data.get("rejectedRows", 0) or 0)
    missing_count = int(data.get("officialGamesMissingFromPriceBoard", len(missing)) or 0)

    # 2 rows per official moneyline game expected.
    expected_rows = official_games * 2
    price_coverage_pct = round((kept_rows / expected_rows) * 100, 2) if expected_rows else 0.0

    if missing_count > 0:
        decision = "PRICE_BOARD_INCOMPLETE"
        severity = "BROKEN_FOR_FULL_SLATE"
    elif rejected_rows > 0:
        decision = "STALE_ROWS_REJECTED_BUT_USABLE"
        severity = "WARNING"
    else:
        decision = "OK"
        severity = "OK"

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "severity": severity,
        "officialGames": official_games,
        "expectedMoneylineRows": expected_rows,
        "keptRows": kept_rows,
        "priceCoveragePct": price_coverage_pct,
        "rejectedStaleRows": rejected_rows,
        "missingOfficialGamesCount": missing_count,
        "missingOfficialGames": missing,
        "rule": "No public/official moneyline board is complete until every official MLB game has price rows. Stale/nonexistent games must be rejected.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 240 OFFICIAL SCHEDULE PRICE COVERAGE AUDIT",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision: {decision}",
        f"Severity: {severity}",
        "",
        f"Official MLB games: {official_games}",
        f"Expected moneyline rows: {expected_rows}",
        f"Kept moneyline rows after schedule filter: {kept_rows}",
        f"Price coverage: {price_coverage_pct}%",
        f"Rejected stale/nonexistent rows: {rejected_rows}",
        f"Missing official games: {missing_count}",
        "",
        "Missing official games from price board:",
    ]

    if missing:
        for g in missing:
            lines.append(f"- {g.get('officialGame')} | status={g.get('liveMlbStatus')} | gameDate={g.get('gameDate')} | gamePk={g.get('gamePk')}")
    else:
        lines.append("- none")

    lines += [
        "",
        "Interpretation:",
        "- If missing official games > 0, the odds/price board is incomplete.",
        "- Do not trust full-slate output until the price source includes those official games.",
        "- Actionable picks can still be shown as dashboard/manual only, but the board is NOT full-slate complete.",
        "",
        f"JSON: {OUT_JSON}",
        "Rule: official MLB schedule is source of truth.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
