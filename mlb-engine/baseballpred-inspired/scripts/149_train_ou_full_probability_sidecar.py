from pathlib import Path
from datetime import datetime
import csv
import json
import math

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FEATURE_CSV = ASTRO / "retrosheet" / "ou_full_baseballpred_features.csv"
MODEL_JSON = ASTRO / "ASTRODDS-ou-full-probability-sidecar-model-v1.json"
REPORT = REPORTS / "149_train_ou_full_probability_sidecar_report.txt"

FEATURES = [
    "away_rf_162","away_ra_162","home_rf_162","home_ra_162",
    "league_avg_total_rolling","projected_simple_total",
    "offense_combo","defense_combo","volatility_proxy","run_environment_index",
    "OBP_162_proxy","SLG_162_proxy","Strt_WHIP_35_proxy","Strt_SO_perc_10_proxy",
    "Bpen_WHIP_75_proxy","Bpen_SO_perc_75_proxy","Bpen_WHIP_35_proxy",
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

def dot(a,b):
    return sum(x*y for x,y in zip(a,b))

def sigmoid(z):
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))

def make_target(r):
    # Synthetic O/U training target until real historical total line is attached.
    # Uses rolling league average as "market-like" reference.
    line = fnum(r.get("league_avg_total_rolling"), 9.0)
    total = fnum(r.get("target_total_runs"), fnum(r.get("total_runs")))
    return 1 if total > line else 0

def prepare(rows):
    X, y = [], []
    for r in rows:
        X.append([1.0] + [fnum(r.get(k)) for k in FEATURES])
        y.append(make_target(r))
    return X, y

def train_logreg(rows, alpha=5.0):
    X, y = prepare(rows)
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

    base_rate = sum(y) / len(y)
    w = [0.0] * p
    w[0] = math.log(max(1e-6, base_rate) / max(1e-6, 1 - base_rate))

    lr = 0.05
    for _ in range(650):
        grad = [0.0] * p
        for xi, yi in zip(Xs, y):
            pred = sigmoid(dot(w, xi))
            err = pred - yi
            for j in range(p):
                grad[j] += err * xi[j] / n
        for j in range(1, p):
            grad[j] += alpha * w[j] / n
        for j in range(p):
            w[j] -= lr * grad[j]

    return {
        "features": ["intercept"] + FEATURES,
        "weightsStandardized": w,
        "featureMeans": means,
        "featureStds": stds,
        "syntheticTarget": "actual_total_runs > rolling_league_avg_total",
    }

def predict(model, r):
    raw = [1.0] + [fnum(r.get(k)) for k in FEATURES]
    x = [1.0]
    for j in range(1, len(raw)):
        x.append((raw[j] - model["featureMeans"][j]) / model["featureStds"][j])
    return sigmoid(dot(model["weightsStandardized"], x))

def log_loss(y, p):
    eps = 1e-9
    p = max(eps, min(1-eps, p))
    return -(y*math.log(p) + (1-y)*math.log(1-p))

def metrics(model, rows):
    if not rows:
        return {}
    ys, ps = [], []
    for r in rows:
        y = make_target(r)
        p = predict(model, r)
        ys.append(y)
        ps.append(p)
    acc = sum((p >= 0.5) == bool(y) for p,y in zip(ps,ys)) / len(ys)
    ll = sum(log_loss(y,p) for p,y in zip(ps,ys)) / len(ys)
    brier = sum((p-y)**2 for p,y in zip(ps,ys)) / len(ys)
    base = sum(ys) / len(ys)
    base_ll = sum(log_loss(y,base) for y in ys) / len(ys)
    return {
        "rows": len(rows),
        "accuracy": round(acc,4),
        "logLoss": round(ll,4),
        "brier": round(brier,4),
        "baseRate": round(base,4),
        "baselineLogLoss": round(base_ll,4),
    }

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    rows = [r for r in rows if int(r.get("year", 0) or 0) >= 1980]

    train = [r for r in rows if int(r["year"]) <= 2022]
    valid = [r for r in rows if int(r["year"]) == 2023]
    test = [r for r in rows if int(r["year"]) >= 2024]

    model = train_logreg(train)
    if model is None:
        lines = [
            "ASTRODDS 149 TRAIN O/U FULL PROBABILITY SIDECAR",
            "=" * 68,
            "ERROR: features missing. Run 148 first.",
        ]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_probability_training_only",
        "warning": "Trained on synthetic target vs rolling league average, not real sportsbook line. Do not use live yet.",
        "model": model,
        "metrics": {
            "train": metrics(model, train),
            "valid2023": metrics(model, valid),
            "test2024Plus": metrics(model, test),
        },
        "featureCsv": str(FEATURE_CSV),
    }
    MODEL_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 149 TRAIN O/U FULL PROBABILITY SIDECAR",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Probability model uses BaseballPred-style proxy features.",
        "- WARNING: target uses synthetic rolling league average until real sportsbook total lines are attached.",
        "",
        f"Rows total: {len(rows)}",
        f"Train rows <=2022: {len(train)}",
        f"Valid rows 2023: {len(valid)}",
        f"Test rows >=2024: {len(test)}",
        "",
        "Metrics:",
        f"- train: {out['metrics']['train']}",
        f"- valid2023: {out['metrics']['valid2023']}",
        f"- test2024Plus: {out['metrics']['test2024Plus']}",
        "",
        f"Model JSON: {MODEL_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
