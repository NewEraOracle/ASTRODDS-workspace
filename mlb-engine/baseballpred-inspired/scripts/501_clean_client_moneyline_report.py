from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

TOP6_JSON = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
STATUS_JSON = ASTRO / "ASTRODDS-500-one-command-status-latest.json"

OUT_JSON = ASTRO / "ASTRODDS-501-clean-client-moneyline-report-latest.json"
REPORT = REPORTS / "501_clean_client_moneyline_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    top6 = load(TOP6_JSON).get("top6ValidatedPicks", []) or []
    official = load(ACTION_JSON).get("actionableMoneyline", []) or []
    status = load(STATUS_JSON)

    lines = [
        "ASTRODDS DAILY MONEYLINE REPORT",
        "=" * 60,
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "System:",
        f"- Status: {status.get('overall', 'UNKNOWN')}",
        f"- Board: PM {status.get('rowsWithPrice')}/{status.get('rows')} | Fair {status.get('rowsWithModel')}/{status.get('rows')} | Edge {status.get('rowsWithEdge')}/{status.get('rows')}",
        "",
        "Official bankroll picks:",
    ]

    if official:
        for i, p in enumerate(official, 1):
            lines += [
                f"{i}. {p.get('pick')} ML",
                f"   Game: {p.get('game')}",
                f"   Edge: +{p.get('currentEdgePct')}%",
                f"   Stake: {p.get('suggestedStake')}",
                "",
            ]
    else:
        lines += [
            "- None today.",
            "- No 5% official A_PICK was detected after full PM/Fair calibration.",
            "",
        ]

    lines += ["Client leans:"]

    if top6:
        for i, p in enumerate(top6[:6], 1):
            stake = p.get("suggestedStake")
            if stake == "dashboard only" and float(str(p.get("edgePct", "0")).replace(",", ".")) >= 3:
                stake = "0.5%-1% max bankroll"
            lines += [
                f"{i}. {p.get('pick')} ML",
                f"   Game: {p.get('game')}",
                f"   Market Price: {p.get('pm')}%",
                f"   Fair Price: {p.get('fair')}%",
                f"   Edge: +{p.get('edgePct')}%",
                f"   Grade: {p.get('grade')}",
                f"   Action: {p.get('clientAction')}",
                f"   Stake: {stake}",
                "",
            ]
    else:
        lines += [
            "- None today.",
            "- No positive client lean was detected.",
            "",
        ]

    lines += [
        "Rules:",
        "- Official picks and client leans are separate.",
        "- Client leans use smaller sizing than official picks.",
        "- No parlays.",
        "- Paper/manual only. No real-money automation.",
    ]

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "officialRows": len(official),
        "clientLeanRows": len(top6),
        "reportText": "\n".join(lines),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
