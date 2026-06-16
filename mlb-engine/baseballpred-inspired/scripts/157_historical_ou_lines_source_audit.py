from pathlib import Path
from datetime import datetime
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"

REPORT = REPORTS / "157_historical_ou_lines_source_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-historical-ou-lines-source-audit-latest.json"

def sniff(path):
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            rows = []
            for _, r in zip(range(2), reader):
                rows.append(r)
            return cols, rows
    except Exception:
        return [], []

def score(cols):
    low = [c.lower() for c in cols]
    s = 0
    for term in ["total", "over", "under", "line", "odds", "price", "close", "open"]:
        if any(term in c for c in low):
            s += 1
    return s

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    files = list(PROCESSED.glob("*.csv")) + list(ASTRO.glob("*.csv")) + list((ROOT / "public").glob("*.json"))
    found = []
    for p in files:
        if p.suffix.lower() != ".csv":
            continue
        cols, rows = sniff(p)
        sc = score(cols)
        if sc >= 2:
            found.append({"path": str(p), "score": sc, "columns": cols[:80], "preview": rows[:1]})

    found.sort(key=lambda x: -x["score"])

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "source_discovery_only",
        "foundCount": len(found),
        "sources": found[:30],
        "decision": "Need historical sportsbook total lines with final scores to run true O/U ROI/CLV backtest.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 157 HISTORICAL O/U LINES SOURCE AUDIT",
        "=" * 70,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Audit only.",
        "- Looks for real historical O/U lines / odds sources.",
        "",
        f"Possible sources: {len(found)}",
    ]

    for s in found[:12]:
        lines.append(f"- score={s['score']} | {s['path']}")
        lines.append(f"  columns={s['columns'][:20]}")

    lines += [
        "",
        "Decision:",
        "- Do not claim market edge until true historical O/U lines are attached.",
        "- Current backtests using synthetic lines are only model sanity checks.",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
