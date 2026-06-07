"""Calibration diagnostics for ASTRODDS baseline moneyline model.

Reads historical moneyline predictions and measures probability calibration. This
is calibration measurement only: no live picks, no today_predictions.json, no
ROI, no CLV, no betting edge, no official picks, and no calibrator pickle.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ENGINE_ROOT / "models"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
HISTORICAL_PREDICTIONS = PROCESSED_DIR / "moneyline_historical_predictions.csv"
REPORT_OUTPUT = CALIBRATION_DIR / "moneyline_calibration_report.json"
BINS_OUTPUT = CALIBRATION_DIR / "moneyline_calibration_bins.csv"
MODEL_PATH = MODELS_DIR / "moneyline_baseline_model.pkl"

BIN_EDGES = [0.0, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 1.0]
BIN_COLUMNS = [
    "bin_lower",
    "bin_upper",
    "count",
    "average_predicted_probability",
    "actual_home_win_rate",
    "calibration_error",
]


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
        if math.isfinite(parsed):
            return parsed
    except ValueError:
        return None
    return None


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def load_predictions() -> list[dict[str, Any]]:
    if not HISTORICAL_PREDICTIONS.exists():
        return []
    rows: list[dict[str, Any]] = []
    with HISTORICAL_PREDICTIONS.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            probability = parse_float(row.get("raw_home_win_probability"))
            target = parse_int(row.get("target_home_win"))
            split = row.get("split") or "unknown"
            if probability is None or target not in {0, 1}:
                continue
            rows.append(
                {
                    "probability": min(1.0, max(0.0, probability)),
                    "target": target,
                    "split": split,
                    "model_version": row.get("model_version") or "unknown",
                    "model_type": row.get("model_type") or "unknown",
                }
            )
    return rows


def rows_by_split(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        split = str(row["split"])
        counts[split] = counts.get(split, 0) + 1
    return counts


def metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluation = [row for row in rows if row["split"] in {"validation", "holdout_2026"}]
    return evaluation if evaluation else rows


def safe_round(value: float | None) -> float | str:
    if value is None:
        return ""
    return round(value, 6)


def brier_score(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum((float(row["probability"]) - int(row["target"])) ** 2 for row in rows) / len(rows)


def log_loss(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    epsilon = 1e-15
    total = 0.0
    for row in rows:
        probability = min(1 - epsilon, max(epsilon, float(row["probability"])))
        target = int(row["target"])
        total += -(target * math.log(probability) + (1 - target) * math.log(1 - probability))
    return total / len(rows)


def bin_index(probability: float) -> int:
    for index in range(len(BIN_EDGES) - 1):
        lower = BIN_EDGES[index]
        upper = BIN_EDGES[index + 1]
        if index == len(BIN_EDGES) - 2:
            if lower <= probability <= upper:
                return index
        elif lower <= probability < upper:
            return index
    return len(BIN_EDGES) - 2


def build_bins(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float | None, float | None, int]:
    groups: list[list[dict[str, Any]]] = [[] for _ in range(len(BIN_EDGES) - 1)]
    for row in rows:
        groups[bin_index(float(row["probability"]))].append(row)

    output: list[dict[str, Any]] = []
    expected_error = 0.0
    max_error = 0.0
    populated = 0
    total = len(rows)

    for index, group in enumerate(groups):
        lower = BIN_EDGES[index]
        upper = BIN_EDGES[index + 1]
        count = len(group)
        avg_probability: float | None = None
        actual_rate: float | None = None
        calibration_error: float | None = None
        if count:
            populated += 1
            avg_probability = sum(float(row["probability"]) for row in group) / count
            actual_rate = sum(int(row["target"]) for row in group) / count
            calibration_error = abs(avg_probability - actual_rate)
            expected_error += (count / total) * calibration_error if total else 0.0
            max_error = max(max_error, calibration_error)

        output.append(
            {
                "bin_lower": lower,
                "bin_upper": upper,
                "count": count,
                "average_predicted_probability": safe_round(avg_probability),
                "actual_home_win_rate": safe_round(actual_rate),
                "calibration_error": safe_round(calibration_error),
            }
        )

    if not rows:
        return output, None, None, populated
    return output, expected_error, max_error, populated


def calibration_quality(evaluation_rows: int, populated_bins: int, ece: float | None, max_error: float | None) -> str:
    if evaluation_rows <= 0:
        return "missing"
    if evaluation_rows < 500:
        return "not_enough_history"
    if populated_bins < 3:
        return "weak"
    if ece is None or max_error is None:
        return "missing"
    if evaluation_rows >= 3000 and populated_bins >= 6 and ece <= 0.015 and max_error <= 0.05:
        return "strong"
    if evaluation_rows >= 1500 and populated_bins >= 4 and ece <= 0.03 and max_error <= 0.08:
        return "medium"
    return "weak"


def write_bins(rows: list[dict[str, Any]]) -> None:
    with BINS_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=BIN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(report: dict[str, Any]) -> None:
    with REPORT_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def model_metadata(rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not rows:
        return "unknown", "unknown"
    return str(rows[0].get("model_version") or "unknown"), str(rows[0].get("model_type") or "unknown")


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - calibrate_model")
    print("Measuring probability calibration only. No live picks, betting edge, ROI, CLV, official picks, or calibrator pickle will be created.")

    if not MODEL_PATH.exists():
        print("No trained moneyline model artifact found. Calibration skipped.")
        print("Next: run train_model.py after verified features exist.")
        return
    rows = load_predictions()
    if not rows:
        print("No verified historical predictions found. Calibration skipped.")
        print("Next: run generate_historical_predictions.py to create moneyline_historical_predictions.csv.")
        return

    evaluation_rows = metric_rows(rows)
    bins, ece, max_error, populated_bins = build_bins(evaluation_rows)
    model_version, model_type = model_metadata(rows)
    split_counts = rows_by_split(rows)
    metric_split_counts = rows_by_split(evaluation_rows)
    warnings = [
        "Calibration metrics use validation + holdout_2026 rows when available; train rows are not used for calibration quality.",
        "This is calibration measurement only. No calibrated probability mapping or calibrator pickle was created.",
        "Betting ROI/edge requires market price or Polymarket implied probability later.",
    ]
    if "holdout_2026" in metric_split_counts:
        warnings.append("2026 is season-to-date holdout only, not a completed full-season calibration set.")
    if populated_bins < 4:
        warnings.append("Predictions occupy few probability bins; calibration quality is conservative.")

    quality = calibration_quality(len(evaluation_rows), populated_bins, ece, max_error)
    report = {
        "input_predictions_file": str(HISTORICAL_PREDICTIONS),
        "bins_output_file": str(BINS_OUTPUT),
        "total_rows": len(rows),
        "metric_rows": len(evaluation_rows),
        "metric_sample_policy": "validation + holdout_2026 when available; otherwise all valid rows",
        "rows_by_split": split_counts,
        "metric_rows_by_split": metric_split_counts,
        "brier_score": safe_round(brier_score(evaluation_rows)),
        "log_loss": safe_round(log_loss(evaluation_rows)),
        "expected_calibration_error": safe_round(ece),
        "max_calibration_error": safe_round(max_error),
        "populated_bins": populated_bins,
        "model_version": model_version,
        "model_type": model_type,
        "calibration_quality": quality,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    write_bins(bins)
    write_report(report)

    print("Calibration diagnostics completed.")
    print(f"- total rows: {len(rows)}")
    print(f"- metric rows: {len(evaluation_rows)}")
    print(f"- brier score: {report['brier_score']}")
    print(f"- log loss: {report['log_loss']}")
    print(f"- expected calibration error: {report['expected_calibration_error']}")
    print(f"- max calibration error: {report['max_calibration_error']}")
    print(f"- calibration quality: {quality}")
    print(f"- report JSON: {REPORT_OUTPUT}")
    print(f"- bins CSV: {BINS_OUTPUT}")
    print("No today_predictions.json file was created. No official pick behavior changed.")


if __name__ == "__main__":
    main()