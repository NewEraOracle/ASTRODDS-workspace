"""Train the first real ASTRODDS baseline moneyline model.

This trains a supervised model for target_home_win using only pre-game feature
columns from mlb_moneyline_features.csv. It does not create predictions, odds,
ROI, CLV, betting edge, calibration, or official picks.
"""
from __future__ import annotations

import csv
import json
import math
import pickle
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
FEATURE_INPUT = PROCESSED_DIR / "mlb_moneyline_features.csv"
MODEL_OUTPUT = MODELS_DIR / "moneyline_baseline_model.pkl"
FEATURE_COLUMNS_OUTPUT = MODELS_DIR / "moneyline_feature_columns.json"
REPORT_OUTPUT = MODELS_DIR / "moneyline_training_report.json"
MODEL_VERSION = "moneyline_logistic_baseline_v0.1"

LEAKAGE_COLUMNS = {
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "winner",
    "target_home_win",
}

TRAIN_SEASONS = {2023, 2024}
VALIDATION_SEASON = 2025
HOLDOUT_SEASON = 2026


class MissingPackageError(RuntimeError):
    pass


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


def load_rows() -> list[dict[str, str]]:
    if not FEATURE_INPUT.exists():
        return []
    with FEATURE_INPUT.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def choose_feature_columns(rows: list[dict[str, str]], warnings: list[str]) -> list[str]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    candidates = [column for column in columns if column not in LEAKAGE_COLUMNS]
    usable: list[str] = []
    dropped_all_missing: list[str] = []
    dropped_non_numeric: list[str] = []

    train_rows = [row for row in rows if parse_int(row.get("season")) in TRAIN_SEASONS]
    for column in candidates:
        train_values = [parse_float(row.get(column)) for row in train_rows]
        numeric_values = [value for value in train_values if value is not None]
        if numeric_values:
            usable.append(column)
        else:
            all_values = [parse_float(row.get(column)) for row in rows]
            if any(value is not None for value in all_values):
                dropped_all_missing.append(column)
            else:
                dropped_non_numeric.append(column)

    if dropped_all_missing:
        warnings.append(f"Dropped columns with no numeric training values: {', '.join(dropped_all_missing)}.")
    if dropped_non_numeric:
        warnings.append(f"Dropped non-numeric or empty columns: {', '.join(dropped_non_numeric)}.")
    return usable


def split_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    train: list[dict[str, str]] = []
    validation: list[dict[str, str]] = []
    holdout: list[dict[str, str]] = []
    skipped = 0

    for row in rows:
        season = parse_int(row.get("season"))
        target = parse_int(row.get("target_home_win"))
        if season is None or target not in {0, 1}:
            skipped += 1
            continue
        if season in TRAIN_SEASONS:
            train.append(row)
        elif season == VALIDATION_SEASON:
            validation.append(row)
        elif season == HOLDOUT_SEASON:
            holdout.append(row)

    if skipped:
        warnings.append(f"Skipped {skipped} rows with missing season or target_home_win.")
    return train, validation, holdout, warnings


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def stddev(values: list[float], avg: float) -> float:
    if len(values) <= 1:
        return 1.0
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    std = math.sqrt(variance)
    return std if std > 1e-9 else 1.0


def fit_preprocessor(rows: list[dict[str, str]], feature_columns: list[str]) -> dict[str, dict[str, float]]:
    imputation: dict[str, float] = {}
    means: dict[str, float] = {}
    stds: dict[str, float] = {}

    for column in feature_columns:
        observed = [parse_float(row.get(column)) for row in rows]
        values = [value for value in observed if value is not None]
        fill = median(values)
        imputation[column] = fill
        imputed = [value if value is not None else fill for value in observed]
        avg = mean(imputed)
        means[column] = avg
        stds[column] = stddev(imputed, avg)

    return {"imputation": imputation, "means": means, "stds": stds}


def transform_rows(rows: list[dict[str, str]], feature_columns: list[str], preprocessor: dict[str, dict[str, float]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in rows:
        features: list[float] = []
        for column in feature_columns:
            raw = parse_float(row.get(column))
            value = raw if raw is not None else preprocessor["imputation"][column]
            features.append((value - preprocessor["means"][column]) / preprocessor["stds"][column])
        matrix.append(features)
    return matrix


def targets(rows: list[dict[str, str]]) -> list[int]:
    return [int(parse_int(row.get("target_home_win")) or 0) for row in rows]


def sigmoid(value: float) -> float:
    if value >= 35:
        return 1.0 - 1e-15
    if value <= -35:
        return 1e-15
    return 1 / (1 + math.exp(-value))


def predict_proba_matrix(matrix: list[list[float]], weights: list[float], intercept: float) -> list[float]:
    probabilities: list[float] = []
    for features in matrix:
        score = intercept + sum(weight * feature for weight, feature in zip(weights, features))
        probabilities.append(sigmoid(score))
    return probabilities


def train_stdlib_logistic_regression(
    matrix: list[list[float]],
    y: list[int],
    learning_rate: float = 0.05,
    iterations: int = 700,
    l2: float = 0.001,
) -> tuple[list[float], float]:
    if not matrix or not y:
        raise ValueError("Training matrix is empty.")
    feature_count = len(matrix[0])
    weights = [0.0] * feature_count
    positive_rate = min(0.99, max(0.01, sum(y) / len(y)))
    intercept = math.log(positive_rate / (1 - positive_rate))
    n = len(y)

    for _ in range(iterations):
        grad_weights = [0.0] * feature_count
        grad_intercept = 0.0
        for features, target in zip(matrix, y):
            probability = sigmoid(intercept + sum(weight * feature for weight, feature in zip(weights, features)))
            error = probability - target
            grad_intercept += error
            for index, feature in enumerate(features):
                grad_weights[index] += error * feature
        intercept -= learning_rate * (grad_intercept / n)
        for index, weight in enumerate(weights):
            regularized_grad = (grad_weights[index] / n) + (l2 * weight)
            weights[index] -= learning_rate * regularized_grad

    return weights, intercept


def accuracy(y: list[int], probabilities: list[float]) -> float | None:
    if not y:
        return None
    correct = sum(1 for target, probability in zip(y, probabilities) if (1 if probability >= 0.5 else 0) == target)
    return correct / len(y)


def log_loss(y: list[int], probabilities: list[float]) -> float | None:
    if not y:
        return None
    epsilon = 1e-15
    total = 0.0
    for target, probability in zip(y, probabilities):
        p = min(1 - epsilon, max(epsilon, probability))
        total += -(target * math.log(p) + (1 - target) * math.log(1 - p))
    return total / len(y)


def brier_score(y: list[int], probabilities: list[float]) -> float | None:
    if not y:
        return None
    return sum((probability - target) ** 2 for target, probability in zip(y, probabilities)) / len(y)


def baseline_home_accuracy(y: list[int]) -> float | None:
    if not y:
        return None
    return sum(1 for target in y if target == 1) / len(y)


def rounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def evaluate(y: list[int], probabilities: list[float]) -> dict[str, float | None]:
    return {
        "accuracy": rounded(accuracy(y, probabilities)),
        "log_loss": rounded(log_loss(y, probabilities)),
        "brier_score": rounded(brier_score(y, probabilities)),
        "baseline_home_team_accuracy": rounded(baseline_home_accuracy(y)),
    }


def try_sklearn_train(
    train_matrix: list[list[float]],
    train_y: list[int],
) -> tuple[Any, str] | None:
    try:
        from sklearn.linear_model import LogisticRegression  # type: ignore
    except ModuleNotFoundError:
        return None

    model = LogisticRegression(max_iter=1000, solver="lbfgs")
    model.fit(train_matrix, train_y)
    return model, "sklearn_logistic_regression"


def model_probabilities(model: Any, model_type: str, matrix: list[list[float]], weights: list[float], intercept: float) -> list[float]:
    if model_type == "sklearn_logistic_regression":
        probabilities = model.predict_proba(matrix)
        return [float(row[1]) for row in probabilities]
    return predict_proba_matrix(matrix, weights, intercept)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - train_model")
    print("Training baseline moneyline/game-winner model only. No odds, ROI, CLV, calibration, predictions, or official picks will be created.")

    rows = load_rows()
    if not rows:
        print("No moneyline feature file found. No model was trained.")
        print("Next: run python mlb-engine/scripts/build_features.py after fetching real MLB game data.")
        return

    warnings: list[str] = []
    feature_columns = choose_feature_columns(rows, warnings)
    train_rows, validation_rows, holdout_rows, split_warnings = split_rows(rows)
    warnings.extend(split_warnings)

    if not feature_columns:
        print("No usable pre-game numeric feature columns found. No model was trained.")
        return
    if not train_rows:
        print("No 2023/2024 training rows found. No model was trained.")
        return
    if not validation_rows:
        print("No 2025 validation rows found. No model was trained.")
        return

    preprocessor = fit_preprocessor(train_rows, feature_columns)
    train_matrix = transform_rows(train_rows, feature_columns, preprocessor)
    validation_matrix = transform_rows(validation_rows, feature_columns, preprocessor)
    holdout_matrix = transform_rows(holdout_rows, feature_columns, preprocessor)
    train_y = targets(train_rows)
    validation_y = targets(validation_rows)
    holdout_y = targets(holdout_rows)

    sklearn_model = try_sklearn_train(train_matrix, train_y)
    weights: list[float] = []
    intercept = 0.0
    if sklearn_model is not None:
        model, model_type = sklearn_model
    else:
        warnings.append("scikit-learn is not installed; used ASTRODDS stdlib logistic regression fallback. Install scikit-learn later for comparable production training: python -m pip install scikit-learn")
        weights, intercept = train_stdlib_logistic_regression(train_matrix, train_y)
        model = None
        model_type = "stdlib_logistic_regression"

    train_probabilities = model_probabilities(model, model_type, train_matrix, weights, intercept)
    validation_probabilities = model_probabilities(model, model_type, validation_matrix, weights, intercept)
    holdout_probabilities = model_probabilities(model, model_type, holdout_matrix, weights, intercept) if holdout_rows else []

    report = {
        "model_version": MODEL_VERSION,
        "model_type": model_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": "target_home_win",
        "market": "moneyline",
        "train_seasons": sorted(TRAIN_SEASONS),
        "validation_season": VALIDATION_SEASON,
        "holdout_2026_policy": "completed 2026 rows are held out as season-to-date/paper evaluation only; they are not used for training",
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "holdout_2026_rows": len(holdout_rows),
        "accuracy": evaluate(validation_y, validation_probabilities)["accuracy"],
        "log_loss": evaluate(validation_y, validation_probabilities)["log_loss"],
        "brier_score": evaluate(validation_y, validation_probabilities)["brier_score"],
        "baseline_home_team_accuracy": evaluate(validation_y, validation_probabilities)["baseline_home_team_accuracy"],
        "train_metrics": evaluate(train_y, train_probabilities),
        "validation_metrics": evaluate(validation_y, validation_probabilities),
        "holdout_2026_metrics": evaluate(holdout_y, holdout_probabilities) if holdout_rows else None,
        "feature_columns": feature_columns,
        "excluded_columns": sorted(LEAKAGE_COLUMNS),
        "warnings": warnings,
    }

    model_payload = {
        "model_version": MODEL_VERSION,
        "model_type": model_type,
        "sklearn_model": model,
        "weights": weights,
        "intercept": intercept,
        "feature_columns": feature_columns,
        "preprocessor": preprocessor,
        "target": "target_home_win",
        "market": "moneyline",
        "created_at": report["generated_at"],
        "official_pick_override": False,
    }

    feature_payload = {
        "model_version": MODEL_VERSION,
        "feature_columns": feature_columns,
        "excluded_columns": sorted(LEAKAGE_COLUMNS),
        "imputation_values": preprocessor["imputation"],
        "scaling_means": preprocessor["means"],
        "scaling_stds": preprocessor["stds"],
        "target": "target_home_win",
        "market": "moneyline",
        "runline_enabled": False,
    }

    with MODEL_OUTPUT.open("wb") as file:
        pickle.dump(model_payload, file)
    write_json(FEATURE_COLUMNS_OUTPUT, feature_payload)
    write_json(REPORT_OUTPUT, report)

    print("Training completed.")
    print(f"- model type: {model_type}")
    print(f"- train rows: {len(train_rows)}")
    print(f"- validation rows: {len(validation_rows)}")
    print(f"- holdout 2026 rows: {len(holdout_rows)}")
    print(f"- validation accuracy: {report['accuracy']}")
    print(f"- validation log_loss: {report['log_loss']}")
    print(f"- validation brier_score: {report['brier_score']}")
    print(f"- baseline home-team accuracy: {report['baseline_home_team_accuracy']}")
    print(f"- model artifact: {MODEL_OUTPUT}")
    print(f"- feature columns: {FEATURE_COLUMNS_OUTPUT}")
    print(f"- training report: {REPORT_OUTPUT}")
    for warning in warnings:
        print(f"Warning: {warning}")
    print("No today_predictions.json file was created. No official pick behavior changed.")


if __name__ == "__main__":
    main()