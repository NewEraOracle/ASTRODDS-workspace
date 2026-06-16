from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

LIVE_OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
V2_STRICT_JSON = ASTRO / "ASTRODDS-ou-v2-strict-paper-score-latest.json"
AB_CSV = ASTRO / "ASTRODDS-ou-v1-v2-ab-test-record.csv"
REPORT = REPORTS / "153_ou_v1_v2_ab_test_tracker_report.txt"

ET = ZoneInfo("America/New_York")

FIELDS = [
    "date", "bucket", "source", "game", "pick", "line", "projected", "edge_runs",
    "grade", "score", "result", "final_score", "total_runs", "status", "notes"
]

def today_et():
    return datetime.now(ET).date().isoformat()

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for f in FIELDS:
        if f not in fields:
            fields.append(f)
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def key(row):
    return "|".join([
        str(row.get("date", "")).strip(),
        str(row.get("bucket", "")).strip(),
        str(row.get("game", "")).strip(),
        str(row.get("pick", "")).strip(),
        str(row.get("line", "")).strip(),
    ])

def add_row(rows, row):
    existing = {key(r) for r in rows}
    k = key(row)
    if k in existing:
        return False
    rows.append(row)
    return True

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    date = today_et()
    ab_rows = read_csv(AB_CSV)
    added = 0

    # V1 live O/U A+ from clean O/U CSV
    live_rows = [
        r for r in read_csv(LIVE_OU_CSV)
        if str(r.get("status", "")).strip() == "clean_ou_aplus"
    ]
    for r in live_rows:
        row = {
            "date": r.get("date", date),
            "bucket": "V1_LIVE_OU_A_PLUS",
            "source": "136_live",
            "game": r.get("game", ""),
            "pick": r.get("pick", ""),
            "line": r.get("line", ""),
            "projected": r.get("projected", ""),
            "edge_runs": r.get("edge_runs", ""),
            "grade": r.get("grade", "A+"),
            "score": "",
            "result": r.get("result", "pending"),
            "final_score": r.get("final_score", ""),
            "total_runs": r.get("total_runs", ""),
            "status": "paper_live_tracking",
            "notes": "Live O/U A+ from 136/clean O/U CSV.",
        }
        if add_row(ab_rows, row):
            added += 1

    # V2 strict paper picks
    data = load_json(V2_STRICT_JSON, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    for c in candidates:
        strict_grade = c.get("strictV2Grade", "")
        if strict_grade not in ("V2_A_PLUS_PAPER", "V2_REVIEW"):
            continue
        bucket = "V2_A_PLUS_PAPER" if strict_grade == "V2_A_PLUS_PAPER" else "V2_REVIEW"
        row = {
            "date": date,
            "bucket": bucket,
            "source": "152_sidecar",
            "game": c.get("game", ""),
            "pick": c.get("pick", ""),
            "line": c.get("line", ""),
            "projected": c.get("projectedTotalRuns", c.get("projected", "")),
            "edge_runs": c.get("edgeRuns", ""),
            "grade": strict_grade,
            "score": c.get("strictV2Score", ""),
            "result": "pending",
            "final_score": "",
            "total_runs": "",
            "status": "paper_ab_test",
            "notes": "V2 sidecar paper-only tracking. Not live Telegram.",
        }
        if add_row(ab_rows, row):
            added += 1

    write_csv(AB_CSV, ab_rows)

    lines = [
        "ASTRODDS 153 O/U V1 VS V2 A/B TEST TRACKER",
        "=" * 64,
        f"Generated ET: {datetime.now(ET).isoformat()}",
        f"AB CSV: {AB_CSV}",
        "",
        "Rules:",
        "- Sidecar/paper tracking only.",
        "- Does not send Telegram.",
        "- Tracks V1 live O/U A+ vs V2 strict paper picks.",
        "",
        f"Rows total: {len(ab_rows)}",
        f"Added now: {added}",
        "",
        "Latest rows:",
    ]

    for r in ab_rows[-12:]:
        lines.append(
            f"- {r.get('date')} | {r.get('bucket')} | {r.get('result')} | "
            f"{r.get('pick')} | {r.get('game')} | line={r.get('line')} score={r.get('score')}"
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
