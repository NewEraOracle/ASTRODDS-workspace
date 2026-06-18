from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "231_moneyline_strict_live_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    data = load(ACTION_JSON)
    bad = []
    for r in data.get("actionableMoneyline", []):
        live = str(r.get("liveMlbStatus", "")).lower()
        if not any(x in live for x in ["scheduled", "pre-game", "pregame", "warmup"]):
            bad.append(r)

    ok = ACTION_JSON.exists() and not bad
    lines = [
        "ASTRODDS 231 MONEYLINE STRICT LIVE HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {'OK' if ok else 'CHECK'}",
        f"Actionable rows: {data.get('actionableRows', 'unknown')}",
        f"Bad actionable live statuses: {len(bad)}",
        "",
        "Rule: every actionable Moneyline must have liveMlbStatus Scheduled/Pre-Game/Warmup.",
    ]
    if bad:
        lines.append("")
        lines.append("Bad rows:")
        for r in bad:
            lines.append(f"- {r.get('pick')} | {r.get('game')} | live={r.get('liveMlbStatus','')}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
