from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import requests

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

ML_CSV = ASTRO / "ASTRODDS-clean-moneyline-record.csv"
OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
REPORT = REPORTS / "158_postponed_suspended_safety_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-postponed-suspended-safety-latest.json"

ET = ZoneInfo("America/New_York")

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def schedule(date):
    try:
        r = requests.get("https://statsapi.mlb.com/api/v1/schedule", params={"sportId":1, "date":date}, timeout=25)
        r.raise_for_status()
        return [g for d in r.json().get("dates", []) for g in d.get("games", [])]
    except Exception:
        return []

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = []
    for kind, path in [("moneyline", ML_CSV), ("ou", OU_CSV)]:
        for r in read_csv(path):
            if str(r.get("result","")).lower() in ("pending", "", "tbd"):
                rows.append({"kind": kind, **r})

    dates = sorted({r.get("date","") for r in rows if r.get("date")})
    statuses = []
    for d in dates:
        for g in schedule(d):
            st = g.get("status", {})
            statuses.append({
                "date": d,
                "gamePk": g.get("gamePk"),
                "abstractGameState": st.get("abstractGameState"),
                "detailedState": st.get("detailedState"),
                "codedGameState": st.get("codedGameState"),
                "away": g.get("teams",{}).get("away",{}).get("team",{}).get("name"),
                "home": g.get("teams",{}).get("home",{}).get("team",{}).get("name"),
            })

    danger = [
        s for s in statuses
        if any(term in str(s.get("detailedState","")).lower() for term in ["postponed", "suspended", "delayed", "cancelled"])
    ]

    out = {
        "generatedAt": datetime.now(ET).isoformat(),
        "pendingRows": len(rows),
        "datesChecked": dates,
        "dangerStatuses": danger,
        "rules": {
            "postponed": "keep pending/review",
            "suspended": "keep pending",
            "delayed": "keep pending",
            "final": "resolve only when final",
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 158 POSTPONED/SUSPENDED SAFETY AUDIT",
        "=" * 64,
        f"Generated ET: {out['generatedAt']}",
        "",
        f"Pending rows checked: {len(rows)}",
        f"Dates checked: {dates}",
        f"Danger statuses found: {len(danger)}",
        "",
        "Danger statuses:",
    ]
    for d in danger:
        lines.append(f"- {d.get('date')} | {d.get('away')} @ {d.get('home')} | {d.get('detailedState')} | {d.get('codedGameState')}")

    lines += [
        "",
        "Rule:",
        "- Resolver should only mark win/loss/push when MLB status is final.",
        "- Postponed/suspended/delayed stays pending.",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
