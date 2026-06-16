from pathlib import Path
from datetime import datetime
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"

REPORT = REPORTS / "156_batting_obp_slg_source_builder_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-batting-obp-slg-source-audit-latest.json"

CANDIDATES = list(PROCESSED.glob("*.csv")) + list(ASTRO.glob("*.csv"))

def sniff(path):
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            rows = []
            for _, r in zip(range(3), reader):
                rows.append(r)
            return cols, rows
    except Exception:
        return [], []

def useful(cols):
    low = [c.lower() for c in cols]
    has_team = any("team" in c for c in low)
    has_bat = any(x in c for c in low for x in ["obp", "slg", "ops", "hit", "bat", "lineup"])
    return has_team and has_bat

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    found = []
    for p in CANDIDATES:
        cols, rows = sniff(p)
        if useful(cols):
            found.append({"path": str(p), "columns": cols[:80], "preview": rows[:2]})

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "source_discovery_only",
        "foundCount": len(found),
        "sources": found[:20],
        "decision": "If a source contains true OBP/SLG by team/date, build 157 to merge it. Otherwise keep proxy features.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 156 BATTING OBP/SLG SOURCE BUILDER AUDIT",
        "=" * 70,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Audit only.",
        "- Looks for true batting OBP/SLG/OPS style data sources.",
        "",
        f"Found possible sources: {len(found)}",
    ]

    for s in found[:10]:
        lines.append(f"- {s['path']}")
        lines.append(f"  columns={s['columns'][:18]}")

    lines += [
        "",
        "Decision:",
        "- True OBP/SLG source is required before replacing proxy BaseballPred features.",
        "- If no true source exists, do not merge full V2 to live.",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
