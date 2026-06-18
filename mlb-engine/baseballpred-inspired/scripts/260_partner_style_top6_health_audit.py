from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

TOP6_JSON = ASTRO / "ASTRODDS-partner-style-top6-moneyline-latest.json"
REPORT = REPORTS / "260_partner_style_top6_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    data = load(TOP6_JSON)
    top6 = data.get("top6ValidatedPicks", []) or []
    official = data.get("officialMoneyline", []) or []

    if len(top6) >= 6 and official:
        overall = "OK_TOP6_AND_OFFICIAL"
    elif top6:
        overall = "OK_TOP6_ONLY"
    else:
        overall = "CHECK_NO_TOP6"

    lines = [
        "ASTRODDS 260 PARTNER STYLE TOP 6 HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Scored rows: {data.get('scoredRows')}",
        f"Missing price/model rows: {data.get('missingRows')}",
        f"Top 6 rows: {data.get('top6Rows')}",
        f"Official rows: {data.get('officialRows')}",
        "",
        "Top 6:",
    ]

    if top6:
        for c in top6:
            lines.append(f"- #{c.get('rank')} | {c.get('pick')} | {c.get('game')} | Edge={c.get('edgePct')}% | Grade={c.get('grade')} | Action={c.get('clientAction')} | Official={c.get('officialTier')}")
    else:
        lines.append("- none")

    lines += ["", "Official:"]
    if official:
        for c in official:
            lines.append(f"- {c.get('officialTier')} | {c.get('pick')} | edge={c.get('edgePct')}% | stake={c.get('suggestedStake')}")
    else:
        lines.append("- none")

    lines += ["", "Rule: partner board is ranking/validated view; official board controls stake."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
