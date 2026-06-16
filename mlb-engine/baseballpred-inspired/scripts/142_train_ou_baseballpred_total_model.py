from pathlib import Path
from datetime import datetime
import csv
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FEATURE_CSV = ASTRO / "retrosheet" / "ou_baseballpred_features.csv"
MODEL_JSON = ASTRO / "ASTRODDS-ou-baseballpred-total-model-v1.json"
REPORT = REPORTS / "142_train_ou_baseballpred_total_model_report.txt"

FEATURES = [
    "away_rf_162","away_ra_162","home_rf_162","home_ra_162",
    "league_avg_total_rolling","projected_simple_total","home_field_flag"
]

def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def read_rows():
    if not FEATURE_CSV.exists():
        return []
    with FEATURE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))

def train_ridge(rows, alpha=10.0):
    # Lightweight ridge via gradient descent so we don't require sklearn.
    X = []
    y = []
    for r in rows:
        X.append([1.0] + [fnum(r[k]) for k in FEATURES])
        y.append(fnum(r["total_runs"]))

    if not X:
        return None

    n = len(X)
    p = len(X[0])

    means = [0.0] * p
    stds = [1.0] * p
    for j in range(1, p):
        vals = [x[j] for x in X]
        means[j] = sum(vals) / len(vals)
        var = sum((v - means[j]) ** 2 for v in vals) / max(1, len(vals)-1)
        stds[j] = math.sqrt(var) if var > 1e-9 else 1.0

    Xs = []
    for x in X:
        Xs.append([1.0] + [(x[j] - means[j]) / stds[j] for j in range(1, p)])

    w = [0.0] * p
    w[0] = sum(y) / len(y)
    lr = 0.03

    for _ in range(900):
        grad = [0.0] * p
        for xi, yi in zip(Xs, y):
            err = dot(w, xi) - yi
            for j in range(p):
                grad[j] += err * xi[j] / n
        for j in range(1, p):
            grad[j] += alpha * w[j] / n
        for j in range(p):
            w[j] -= lr * grad[j]

    return {
        "interceptAndWeightsStandardized": w,
        "featureMeans": means,
        "featureStds": stds,
        "features": ["intercept"] + FEATURES,
    }

def predict(model, r):
    raw = [1.0] + [fnum(r[k]) for k in FEATURES]
    x = [1.0]
    for j in range(1, len(raw)):
        x.append((raw[j] - model["featureMeans"][j]) / model["featureStds"][j])
    return dot(model["interceptAndWeightsStandardized"], x)

def metrics(model, rows):
    preds = []
    ys = []
    for r in rows:
        preds.append(predict(model, r))
        ys.append(fnum(r["total_runs"]))
    if not preds:
        return {}
    mae = sum(abs(p-y) for p, y in zip(preds, ys)) / len(preds)
    rmse = math.sqrt(sum((p-y)**2 for p, y in zip(preds, ys)) / len(preds))
    baseline = sum(ys) / len(ys)
    base_mae = sum(abs(baseline-y) for y in ys) / len(ys)
    return {
        "rows": len(rows),
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "baselineMean": round(baseline, 4),
        "baselineMae": round(base_mae, 4),
    }

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    rows = [r for r in rows if int(r.get("year", 0) or 0) >= 1980]

    train = [r for r in rows if int(r["year"]) <= 2022]
    valid = [r for r in rows if int(r["year"]) == 2023]
    test = [r for r in rows if int(r["year"]) >= 2024]

    model = train_ridge(train)
    if model is None:
        lines = [
            "ASTRODDS 142 TRAIN O/U BASEBALLPRED TOTAL MODEL",
            "=" * 64,
            "ERROR: no features found. Run 141 first.",
            f"Feature CSV: {FEATURE_CSV}",
        ]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    train_m = metrics(model, train)
    valid_m = metrics(model, valid)
    test_m = metrics(model, test)

    artifact = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_training_only",
        "model": "ASTRODDS_OU_BASEBALLPRED_TOTAL_RIDGE_V1",
        "target": "total_runs",
        "modelParams": model,
        "metrics": {
            "train": train_m,
            "valid2023": valid_m,
            "test2024Plus": test_m,
        },
        "featureCsv": str(FEATURE_CSV),
    }
    MODEL_JSON.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 142 TRAIN O/U BASEBALLPRED TOTAL MODEL",
        "=" * 64,
        f"Generated UTC: {artifact['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Lightweight ridge model over rolling 162 Retrosheet features.",
        "",
        f"Rows total: {len(rows)}",
        f"Train rows <=2022: {len(train)}",
        f"Valid rows 2023: {len(valid)}",
        f"Test rows >=2024: {len(test)}",
        "",
        "Metrics:",
        f"- train: {train_m}",
        f"- valid2023: {valid_m}",
        f"- test2024Plus: {test_m}",
        "",
        f"Model JSON: {MODEL_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
