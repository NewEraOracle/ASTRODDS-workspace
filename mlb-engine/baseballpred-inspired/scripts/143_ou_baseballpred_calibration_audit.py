from pathlib import Path
from datetime import datetime
import csv
import json
import math

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FEATURE_CSV = ASTRO / "retrosheet" / "ou_baseballpred_features.csv"
MODEL_JSON = ASTRO / "ASTRODDS-ou-baseballpred-total-model-v1.json"
OUT_JSON = ASTRO / "ASTRODDS-ou-baseballpred-calibration-audit-latest.json"
REPORT = REPORTS / "143_ou_baseballpred_calibration_audit_report.txt"

def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def read_csv_rows():
    if not FEATURE_CSV.exists():
        return []
    with FEATURE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))

def predict(model, r):
    params = model["modelParams"]
    features = params["features"][1:]
    raw = [1.0] + [fnum(r[k]) for k in features]
    x = [1.0]
    for j in range(1, len(raw)):
        x.append((raw[j] - params["featureMeans"][j]) / params["featureStds"][j])
    return dot(params["interceptAndWeightsStandardized"], x)

def bucket(edge):
    # Synthetic lines for calibration: rounded league-ish market using simple projection.
    ae = abs(edge)
    if ae >= 2.0:
        return "2.00+"
    if ae >= 1.5:
        return "1.50-1.99"
    if ae >= 1.0:
        return "1.00-1.49"
    if ae >= 0.5:
        return "0.50-0.99"
    return "0.00-0.49"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    if not MODEL_JSON.exists():
        lines = [
            "ASTRODDS 143 O/U BASEBALLPRED CALIBRATION AUDIT",
            "=" * 64,
            "ERROR: model missing. Run 142 first.",
        ]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    model = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
    rows = [r for r in read_csv_rows() if int(r.get("year", 0) or 0) >= 2024]

    buckets = {}
    for r in rows:
        pred = predict(model, r)
        actual = fnum(r["total_runs"])
        simple_market = fnum(r["league_avg_total_rolling"])
        edge = pred - simple_market
        b = bucket(edge)
        rec = buckets.setdefault(b, {"n": 0, "overs": 0, "mae_sum": 0.0, "avg_edge_sum": 0.0})
        rec["n"] += 1
        rec["overs"] += 1 if actual > simple_market else 0
        rec["mae_sum"] += abs(pred - actual)
        rec["avg_edge_sum"] += edge

    out_buckets = []
    for b, rec in sorted(buckets.items()):
        n = rec["n"]
        out_buckets.append({
            "bucket": b,
            "n": n,
            "overRateVsSyntheticLine": round(rec["overs"] / n, 4) if n else 0,
            "mae": round(rec["mae_sum"] / n, 4) if n else 0,
            "avgEdge": round(rec["avg_edge_sum"] / n, 4) if n else 0,
        })

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_calibration_only",
        "note": "Uses synthetic rolling league average as reference line, not sportsbook historical lines.",
        "rows2024Plus": len(rows),
        "buckets": out_buckets,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 143 O/U BASEBALLPRED CALIBRATION AUDIT",
        "=" * 64,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Calibration audit, not live betting.",
        "- Uses synthetic rolling league-average line until historical sportsbook totals are attached.",
        "",
        f"Rows 2024+: {len(rows)}",
        "",
        "Buckets:",
    ]
    for b in out_buckets:
        lines.append(
            f"- {b['bucket']} | n={b['n']} | overRate={b['overRateVsSyntheticLine']} | "
            f"mae={b['mae']} | avgEdge={b['avgEdge']}"
        )
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
