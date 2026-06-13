from pathlib import Path
import csv
import json
import math
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "processed" / "astrodss_master_feature_dataset_v1.csv"
OUT_CSV = ROOT / "data" / "processed" / "astrodss_master_feature_dataset_v2_calibrated.csv"
OUT_MODEL = ROOT / "models" / "ASTRODDS_MLB_CALIBRATION_V2.json"
OUT_JSON = ROOT / "reports" / "15_model_calibration_v2.json"
REPORT = ROOT / "reports" / "15_model_calibration_v2_report.txt"

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def inum(x):
    try:
        if x is None or x == "":
            return None
        return int(float(str(x).replace(",", ".")))
    except Exception:
        return None

def clamp(p):
    if p is None:
        return None
    return max(0.01, min(0.99, float(p)))

def gap_bucket(gap):
    if gap is None:
        return "missing"
    if gap < 0.01:
        return "0-1%"
    if gap < 0.02:
        return "1-2%"
    if gap < 0.03:
        return "2-3%"
    if gap < 0.05:
        return "3-5%"
    if gap < 0.08:
        return "5-8%"
    if gap < 0.12:
        return "8-12%"
    if gap < 0.20:
        return "12-20%"
    return "20%+"

def split_name(season):
    if season <= 2023:
        return "train_2017_2023"
    if season == 2024:
        return "validation_2024"
    return "holdout_2025_2026"

def load_rows():
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def summarize(rows, prob_col):
    tested = 0
    correct = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    buckets = defaultdict(lambda: {"tested": 0, "correct": 0, "prob_sum": 0.0})

    for r in rows:
        if str(r.get("model_ready")) != "1":
            continue

        y = inum(r.get("model_correct"))
        p = clamp(fnum(r.get(prob_col)))
        bucket = r.get("calibration_bucket", "missing")

        if y is None or p is None:
            continue

        tested += 1
        correct += y

        brier_sum += (p - y) ** 2
        logloss_sum += -(y * math.log(p) + (1 - y) * math.log(1 - p))

        buckets[bucket]["tested"] += 1
        buckets[bucket]["correct"] += y
        buckets[bucket]["prob_sum"] += p

    accuracy = round((correct / tested) * 100, 2) if tested else 0
    brier = round(brier_sum / tested, 5) if tested else None
    logloss = round(logloss_sum / tested, 5) if tested else None

    bucket_out = {}
    for b, s in buckets.items():
        t = s["tested"]
        c = s["correct"]
        bucket_out[b] = {
            "tested": t,
            "correct": c,
            "accuracy": round((c / t) * 100, 2) if t else 0,
            "avgPredictedProbability": round((s["prob_sum"] / t) * 100, 2) if t else 0
        }

    return {
        "tested": tested,
        "correct": correct,
        "accuracy": accuracy,
        "brier": brier,
        "logloss": logloss,
        "buckets": bucket_out
    }

def main():
    rows = load_rows()

    train_stats = defaultdict(lambda: {"tested": 0, "correct": 0})
    global_train = {"tested": 0, "correct": 0}

    usable = []

    for r in rows:
        season = inum(r.get("season"))
        ready = str(r.get("model_ready")) == "1"
        gap = fnum(r.get("model_score_gap"))
        y = inum(r.get("model_correct"))

        r["calibration_bucket"] = gap_bucket(gap)
        r["data_split"] = split_name(season) if season else "unknown"

        if not ready or gap is None or y is None or not season:
            r["calibrated_pick_probability_v2"] = ""
            continue

        usable.append(r)

        if season <= 2023:
            b = r["calibration_bucket"]
            train_stats[b]["tested"] += 1
            train_stats[b]["correct"] += y
            global_train["tested"] += 1
            global_train["correct"] += y

    global_prob = global_train["correct"] / global_train["tested"]

    calibration = {}

    for bucket, s in train_stats.items():
        tested = s["tested"]
        correct = s["correct"]

        if tested < 100:
            prob = global_prob
            method = "global_fallback_low_sample"
        else:
            prob = correct / tested
            method = "empirical_bucket"

        calibration[bucket] = {
            "tested": tested,
            "correct": correct,
            "probability": round(prob, 6),
            "probabilityPct": round(prob * 100, 2),
            "method": method
        }

    for r in usable:
        bucket = r["calibration_bucket"]
        p = calibration.get(bucket, {}).get("probability", global_prob)
        r["calibrated_pick_probability_v2"] = round(p, 6)

    fieldnames = list(rows[0].keys())
    extra = ["calibration_bucket", "data_split", "calibrated_pick_probability_v2"]
    for e in extra:
        if e not in fieldnames:
            fieldnames.append(e)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    splits = {
        "train_2017_2023": [],
        "validation_2024": [],
        "holdout_2025_2026": []
    }

    for r in rows:
        if r.get("data_split") in splits:
            splits[r["data_split"]].append(r)

    split_reports = {
        name: summarize(split_rows, "calibrated_pick_probability_v2")
        for name, split_rows in splits.items()
    }

    model = {
        "modelName": "ASTRODDS_MLB_CALIBRATION_V2",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "inputDataset": str(INPUT),
        "outputDataset": str(OUT_CSV),
        "calibrationMethod": "empirical score-gap bucket calibration trained on seasons <= 2023",
        "globalTrainProbability": round(global_prob, 6),
        "globalTrainProbabilityPct": round(global_prob * 100, 2),
        "calibrationBuckets": calibration,
        "splitReports": split_reports,
        "rules": [
            "Calibration does not change the model pick.",
            "Calibration converts model score gap into realistic historical win probability.",
            "Validation and holdout must be monitored before real-money use.",
            "Paper only."
        ]
    }

    OUT_MODEL.write_text(json.dumps(model, indent=2), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(model, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 15 MODEL CALIBRATION V2")
    lines.append("=" * 38)
    lines.append("")
    lines.append("Goal:")
    lines.append("Convert raw model score gaps into realistic calibrated win probabilities.")
    lines.append("")
    lines.append(f"Train global probability: {round(global_prob * 100, 2)}%")
    lines.append("")
    lines.append("Calibration buckets trained on seasons <= 2023:")

    order = ["0-1%", "1-2%", "2-3%", "3-5%", "5-8%", "8-12%", "12-20%", "20%+"]
    for b in order:
        if b in calibration:
            c = calibration[b]
            lines.append(
                f"- {b}: probability={c['probabilityPct']}% tested={c['tested']} correct={c['correct']} method={c['method']}"
            )

    lines.append("")
    lines.append("Split performance using calibrated probabilities:")
    for name, s in split_reports.items():
        lines.append(
            f"- {name}: tested={s['tested']} accuracy={s['accuracy']}% brier={s['brier']} logloss={s['logloss']}"
        )

    lines.append("")
    lines.append("Holdout bucket performance:")
    holdout = split_reports["holdout_2025_2026"]["buckets"]
    for b in order:
        if b in holdout:
            s = holdout[b]
            lines.append(
                f"- {b}: actual={s['accuracy']}% predictedAvg={s['avgPredictedProbability']}% tested={s['tested']}"
            )

    lines.append("")
    lines.append("Engine conclusion:")
    lines.append("- Calibration V2 makes model probabilities more honest.")
    lines.append("- This is required before comparing model probability vs market probability.")
    lines.append("- Next step: 16_edge_backtest_v2.py with market odds when available.")
    lines.append("")
    lines.append(f"Model JSON: {OUT_MODEL}")
    lines.append(f"Calibrated CSV: {OUT_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
