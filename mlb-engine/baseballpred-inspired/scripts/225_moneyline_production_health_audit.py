from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER_REPORT = REPORTS / "31_auto_daily_engine_runner_report.txt"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "225_moneyline_production_health_audit_report.txt"

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    data = load_json(ACTION_JSON)
    runner_text = RUNNER_REPORT.read_text(encoding="utf-8", errors="ignore") if RUNNER_REPORT.exists() else ""

    checks = []
    checks.append(("actionable_json_exists", ACTION_JSON.exists()))
    checks.append(("runner_called_223", "Moneyline production board pipeline 223 exit code" in runner_text))
    checks.append(("runner_status_ok", "STATUS: OK" in runner_text))
    checks.append(("moneyline_only_rule", "Moneyline only" in json.dumps(data) or "MONEYLINE" in json.dumps(data)))
    checks.append(("has_generated_at", bool(data.get("generatedAt"))))

    ok = all(v for _, v in checks)

    lines = [
        "ASTRODDS 225 MONEYLINE PRODUCTION HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {'OK' if ok else 'CHECK'}",
        "",
        "Checks:",
    ]
    for k, v in checks:
        lines.append(f"- {k}: {'OK' if v else 'MISSING'}")

    lines += [
        "",
        f"Actionable rows: {data.get('actionableRows', 'unknown')}",
        f"Blocked rows: {data.get('blockedRows', 'unknown')}",
        f"Missing model/price rows: {data.get('missingModelOrPriceRows', 'unknown')}",
        f"No value rows: {data.get('noValueRows', 'unknown')}",
        "",
        "Rule: Moneyline production board must rebuild every runner scan before Telegram result tracking.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
