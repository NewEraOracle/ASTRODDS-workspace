from pathlib import Path
from datetime import datetime
import csv, json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "191_live_pick_calibration_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-live-pick-calibration-latest.json"

SOURCES = {
    "moneyline_clean": ASTRO / "ASTRODDS-clean-moneyline-record.csv",
    "ou_clean": ASTRO / "ASTRODDS-clean-ou-record.csv",
    "market_lines": ASTRO / "ASTRODDS-historical-market-lines-template.csv",
    "ou_ab": ASTRO / "ASTRODDS-ou-v1-v2-ab-test-record.csv",
}

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def fnum(v, default=None):
    try:
        s = str(v).strip().replace("%","")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def summarize(rows, group_key=None):
    groups = defaultdict(list)
    for r in rows:
        res = str(r.get("result","")).lower()
        if res not in ("win","loss","push"):
            continue
        key = str(r.get(group_key,"all")) if group_key else "all"
        groups[key].append(r)

    out = {}
    for k, rs in groups.items():
        wins = sum(1 for r in rs if str(r.get("result","")).lower()=="win")
        losses = sum(1 for r in rs if str(r.get("result","")).lower()=="loss")
        pushes = sum(1 for r in rs if str(r.get("result","")).lower()=="push")
        denom = wins+losses
        avg_edge = []
        for r in rs:
            for c in ["edge_runs","edge","edgePct","score"]:
                if c in r:
                    v = fnum(r.get(c), None)
                    if v is not None:
                        avg_edge.append(v)
                        break
        out[k] = {
            "rows": len(rs),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "winRate": round(100*wins/denom,1) if denom else 0.0,
            "avgEdgeOrScore": round(sum(avg_edge)/len(avg_edge),3) if avg_edge else "",
        }
    return out

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = {}
    summaries = {}
    for name, path in SOURCES.items():
        rows = read_csv(path)
        data[name] = {"path": str(path), "rows": len(rows), "resolved": sum(1 for r in rows if str(r.get("result","")).lower() in ("win","loss","push"))}
        summaries[name] = {
            "by_grade": summarize(rows, "grade"),
            "by_market": summarize(rows, "market"),
            "by_bucket": summarize(rows, "bucket"),
            "all": summarize(rows),
        }

    # Minimum sample rule for calibration changes.
    recommendations = []
    for name, meta in data.items():
        if meta["resolved"] < 30:
            recommendations.append(f"{name}: keep paper / no threshold change; only {meta['resolved']} resolved rows")
        else:
            recommendations.append(f"{name}: enough sample for first threshold review ({meta['resolved']} resolved rows)")

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "data": data,
        "summaries": summaries,
        "recommendations": recommendations,
        "minimumSampleRule": "Do not adjust live thresholds until 30+ resolved rows per market; prefer 100+ for stronger confidence.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 191 LIVE PICK CALIBRATION AUDIT",
        "=" * 66,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Data:",
    ]
    for name, meta in data.items():
        lines.append(f"- {name}: rows={meta['rows']} resolved={meta['resolved']} path={meta['path']}")
    lines += ["", "Recommendations:"]
    for r in recommendations:
        lines.append(f"- {r}")
    lines += ["", "Summary preview:"]
    for name, s in summaries.items():
        lines.append(f"- {name} all: {s['all']}")
    lines += ["", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
