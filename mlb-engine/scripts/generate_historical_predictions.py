"""Generate historical baseline moneyline probabilities.

Loads the trained ASTRODDS baseline moneyline model and scores historical feature
rows. This creates calibration/backtest inputs only. It does not create live
picks, today_predictions.json, betting edge, ROI, CLV, confidence, or official
ASTRODDS picks.
"""
from __future__ import annotations

import csv
import json
import math
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
FEATURE_INPUT = PROCESSED_DIR / "mlb_moneyline_features.csv"
MODEL_PATH = MODELS_DIR / "moneyline_baseline_model.pkl"
FEATURE_COLUMNS_PATH = MODELS_DIR / "moneyline_feature_columns.json"
TRAINING_REPORT_PATH = MODELS_DIR / "moneyline_training_report.json"
OUTPUT_CSV = PROCESSED_DIR / "moneyline_historical_predictions.csv"
OUTPUT_REPORT = PROCESSED_DIR / "moneyline_historical_predictions_report.json"

OUTPUT_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "target_home_win",
    "raw_home_win_probability",
    "predicted_home_win",
    "split",
    "model_version",
    "model_type",
    "generated_at",
]


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


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


def sigmoid(value: float) -> float:
    if value >= 35:
        return 1.0 - 1e-15
    if value <= -35:
        return 1e-15
    return 1 / (1 + math.exp(-value))


def split_for_season(season: int) -> str | None:
    if season in {2023, 2024}:
        return "train"
    if season == 2025:
        return "validation"
    if season == 2026:
        return "holdout_2026"
    return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    return None


def load_model(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as file:
            payload = pickle.load(file)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        return None
    except ModuleNotFoundError as error:
        print(f"Model load skipped. Missing package needed for pickled model: {error.name}")
        print("No historical predictions were written.")
        return None
    except Exception as error:
        print(f"Model load skipped safely: {error}")
        print("No historical predictions were written.")
        return None
    return None


def load_feature_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def transform_row(row: dict[str, str], feature_columns: list[str], feature_config: dict[str, Any]) -> list[float]:
    imputation = feature_config.get("imputation_values", {})
    means = feature_config.get("scaling_means", {})
    stds = feature_config.get("scaling_stds", {})
    features: list[float] = []

    for column in feature_columns:
        raw = parse_float(row.get(column))
        fill = float(imputation.get(column, 0.0))
        mean = float(means.get(column, 0.0))
        std = float(stds.get(column, 1.0))
        if abs(std) < 1e-12:
            std = 1.0
        value = raw if raw is not None else fill
        features.append((value - mean) / std)

    return features


def stdlib_probability(features: list[float], weights: list[float], intercept: float) -> float:
    score = intercept + sum(weight * feature for weight, feature in zip(weights, features))
    return sigmoid(score)


def model_probability(model_payload: dict[str, Any], features: list[float]) -> float | None:
    model_type = str(model_payload.get("model_type") or "")
    if model_type == "sklearn_logistic_regression":
        model = model_payload.get("sklearn_model")
        if model is None:
            return None
        probabilities = model.predict_proba([features])
        return float(probabilities[0][1])

    weights = model_payload.get("weights")
    intercept = model_payload.get("intercept", 0.0)
    if not isinstance(weights, list):
        return None
    numeric_weights = [float(weight) for weight in weights]
    return stdlib_probability(features, numeric_weights, float(intercept))


def write_csv(rows: list[dict[str, Any]]) -> None:
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(report: dict[str, Any]) -> None:
    with OUTPUT_REPORT.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - generate_historical_predictions")
    print("Scoring historical baseline moneyline probabilities only. No live picks, odds, ROI, CLV, calibration, confidence, or official picks will be created.")

    warnings: list[str] = []
    feature_config = load_json(FEATURE_COLUMNS_PATH)
    training_report = load_json(TRAINING_REPORT_PATH) or {}
    model_payload = load_model(MODEL_PATH)
    rows = load_feature_rows(FEATURE_INPUT)

    if feature_config is None:
        print(f"Missing or invalid feature column file: {FEATURE_COLUMNS_PATH}")
        print("No historical predictions were written.")
        return
    if model_payload is None:
        print(f"Missing or invalid model file: {MODEL_PATH}")
        print("No historical predictions were written.")
        return
    if not rows:
        print(f"Missing or empty feature input: {FEATURE_INPUT}")
        print("No historical predictions were written.")
        return

    feature_columns = feature_config.get("feature_columns")
    if not isinstance(feature_columns, list) or not all(isinstance(column, str) for column in feature_columns):
        print("Feature column file does not contain a valid feature_columns list.")
        print("No historical predictions were written.")
        return

    model_version = str(model_payload.get("model_version") or training_report.get("model_version") or "unknown")
    model_type = str(model_payload.get("model_type") or training_report.get("model_type") or "unknown")
    generated_at = datetime.now(timezone.utc).isoformat()
    output_rows: list[dict[str, Any]] = []
    rows_by_split = {"train": 0, "validation": 0, "holdout_2026": 0}
    skipped_rows = 0

    for row in rows:
        season = parse_int(row.get("season"))
        target = parse_int(row.get("target_home_win"))
        if season is None or target not in {0, 1}:
            skipped_rows += 1
            continue
        split = split_for_season(season)
        if split is None:
            skipped_rows += 1
            continue
        probability = model_probability(model_payload, transform_row(row, feature_columns, feature_config))
        if probability is None:
            skipped_rows += 1
            continue

        rows_by_split[split] += 1
        output_rows.append(
            {
                "game_id": row.get("game_id", ""),
                "game_date": row.get("game_date", ""),
                "season": season,
                "home_team": row.get("home_team", ""),
                "away_team": row.get("away_team", ""),
                "target_home_win": target,
                "raw_home_win_probability": round(probability, 6),
                "predicted_home_win": 1 if probability >= 0.5 else 0,
                "split": split,
                "model_version": model_version,
                "model_type": model_type,
                "generated_at": generated_at,
            }
        )

    if skipped_rows:
        warnings.append(f"Skipped {skipped_rows} rows with invalid target, unsupported season, or unavailable model probability.")
    if rows_by_split["holdout_2026"]:
        warnings.append("2026 rows are holdout_2026 season-to-date only; they are not live picks and not official ASTRODDS bets.")

    write_csv(output_rows)
    report = {
        "input_feature_file": str(FEATURE_INPUT),
        "model_path": str(MODEL_PATH),
        "feature_columns_path": str(FEATURE_COLUMNS_PATH),
        "training_report_path": str(TRAINING_REPORT_PATH),
        "output_csv_path": str(OUTPUT_CSV),
        "total_rows_scored": len(output_rows),
        "rows_by_split": rows_by_split,
        "model_version": model_version,
        "model_type": model_type,
        "warnings": warnings,
        "generated_at": generated_at,
    }
    write_report(report)

    print("Historical predictions generated.")
    print(f"- total rows scored: {len(output_rows)}")
    print(f"- train rows: {rows_by_split['train']}")
    print(f"- validation rows: {rows_by_split['validation']}")
    print(f"- holdout_2026 rows: {rows_by_split['holdout_2026']}")
    print(f"- output CSV: {OUTPUT_CSV}")
    print(f"- output report: {OUTPUT_REPORT}")
    for warning in warnings:
        print(f"Warning: {warning}")
    print("No today_predictions.json file was created. No official pick behavior changed.")


if __name__ == "__main__":
    main()