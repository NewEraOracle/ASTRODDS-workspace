from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

COVERAGE_JSON = ASTRO / "ASTRODDS-moneyline-official-schedule-price-coverage-latest.json"
TRACE_JSON = ASTRO / "ASTRODDS-price-source-trace-latest.json"
REPORT = REPORTS / "245_price_source_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    cov = load(COVERAGE_JSON)
    trace = load(TRACE_JSON)

    missing = int(cov.get("missingOfficialGamesCount", 0) or 0)
    coverage = cov.get("priceCoveragePct", 0)
    hits = trace.get("hitFiles", []) or []

    if missing == 0:
        decision = "OK"
        next_fix = "none"
    elif hits:
        decision = "MATCHER_OR_NORMALIZER_BROKEN"
        next_fix = "Fix moneyline board builder to read/match the raw files where missing games were found."
    else:
        decision = "ODDS_SOURCE_MISSING_GAMES"
        next_fix = "Fix odds collector/source query. The missing official games are not present in raw .astrodds price files."

    lines = [
        "ASTRODDS 245 PRICE SOURCE HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Decision: {decision}",
        f"Price coverage: {coverage}%",
        f"Missing official games: {missing}",
        f"Trace hit files: {len(hits)}",
        "",
        f"Next fix: {next_fix}",
        "",
        "Missing official games:",
    ]

    for g in cov.get("missingOfficialGames", []) or []:
        lines.append(f"- {g.get('officialGame')} | {g.get('liveMlbStatus')} | {g.get('gameDate')} | gamePk={g.get('gamePk')}")

    lines += ["", "Trace hits:"]
    if hits:
        for h in hits[:50]:
            lines.append(f"- {h.get('file')} | teams={h.get('teamHits')} | games={h.get('gameHits')}")
    else:
        lines.append("- none")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
