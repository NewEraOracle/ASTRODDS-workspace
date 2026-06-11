"""Train and compare a pitcher-enhanced ASTRODDS baseline moneyline model.

This script is research-only. It evaluates whether the existing MLB pitcher
feature layer improves a simple moneyline/game-winner model. It does not create
live picks, official picks, predictions, odds, ROI, CLV, calibration mapping,
Telegram alerts, or real-money behavior.
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
FEATURE_INPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers.csv"
BASELINE_REPORT_INPUT = MODELS_DIR / "moneyline_training_report.json"
MODEL_OUTPUT = MODELS_DIR / "moneyline_pitcher_model.pkl"
FEATURE_COLUMNS_OUTPUT = MODELS_DIR / "moneyline_pitcher_feature_columns.json"
REPORT_OUTPUT = MODELS_DIR / "moneyline_pitcher_training_report.json"
COMPARISON_OUTPUT = MODELS_DIR / "moneyline_model_comparison_report.json"
MODEL_VERSION = "moneyline_pitcher_candidate_v0.1"

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

PITCHER_TEXT_COLUMNS = {
    "home_starting_pitcher_id",
    "away_starting_pitcher_id",
    "home_starting_pitcher_name",
    "away_starting_pitcher_name",
    "home_pitcher_status",
    "away_pitcher_status",
    "pitcher_data_quality",
    "pitcher_warnings",
}

DERIVED_PITCHER_FEATURE_COLUMNS = [
    "home_pitcher_status_confirmed",
    "away_pitcher_status_confirmed",
    "pitcher_data_quality_score",
]

TRAIN_SEASONS = {2023, 2024}
VALIDATION_SEASON = 2025
HOLDOUT_SEASON = 2026


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


def normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def load_rows() -> list[dict[str, str]]:
    if not FEATURE_INPUT.exists():
        return []
    with FEATURE_INPUT.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def choose_feature_columns(rows: list[dict[str, str]], warnings: list[str]) -> list[str]:
    if not rows:
        return []

    columns = list(rows[0].keys())
    candidates = [column for column in columns if column not in LEAKAGE_COLUMNS and column not in PITCHER_TEXT_COLUMNS]
    train_rows = [row for row in rows if parse_int(row.get("season")) in TRAIN_SEASONS]

    usable: list[str] = []
    dropped_all_missing: list[str] = []
    dropped_non_numeric: list[str] = []

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

    usable.extend(column for column in DERIVED_PITCHER_FEATURE_COLUMNS if column not in usable)
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
        observed = [parse_feature_value(row, column) for row in rows]
        values = [value for value in observed if value is not None]
        fill = median(values)
        imputation[column] = fill
        imputed = [value if value is not None else fill for value in observed]
        avg = mean(imputed)
        means[column] = avg
        stds[column] = stddev(imputed, avg)

    return {"imputation": imputation, "means": means, "stds": stds}


def derived_pitcher_value(row: dict[str, str], column: str) -> float | None:
    if column == "home_pitcher_status_confirmed":
        return 1.0 if normalize_text(row.get("home_pitcher_status")) == "confirmed" else 0.0
    if column == "away_pitcher_status_confirmed":
        return 1.0 if normalize_text(row.get("away_pitcher_status")) == "confirmed" else 0.0
    if column == "pitcher_data_quality_score":
        quality = normalize_text(row.get("pitcher_data_quality"))
        return {
            "high": 1.0,
            "medium": 0.66,
            "low": 0.33,
            "missing": 0.0,
        }.get(quality, 0.0)
    return None


def parse_feature_value(row: dict[str, str], column: str) -> float | None:
    derived = derived_pitcher_value(row, column)
    if derived is not None:
        return derived
    return parse_float(row.get(column))


def transform_rows(rows: list[dict[str, str]], feature_columns: list[str], preprocessor: dict[str, dict[str, float]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in rows:
        features: list[float] = []
        for column in feature_columns:
            raw = parse_feature_value(row, column)
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


def metric_value(report: dict[str, Any], *paths: tuple[str, ...]) -> float | None:
    for path in paths:
        current: Any = report
        found = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]
        if found and isinstance(current, (int, float)) and math.isfinite(float(current)):
            return float(current)
    return None


def metric_int(report: dict[str, Any], *paths: tuple[str, ...]) -> int | None:
    value = metric_value(report, *paths)
    return int(value) if value is not None else None


def summary_from_training_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_version": str(report.get("model_version") or report.get("modelVersion") or "unknown"),
        "model_type": str(report.get("model_type") or report.get("modelType") or "unknown"),
        "train_rows": metric_int(report, ("train_rows",)),
        "validation_rows": metric_int(report, ("validation_rows",)),
        "holdout_2026_rows": metric_int(report, ("holdout_2026_rows",)),
        "validation_accuracy": metric_value(report, ("validation_metrics", "accuracy"), ("accuracy",)),
        "validation_log_loss": metric_value(report, ("validation_metrics", "log_loss"), ("log_loss",)),
        "validation_brier_score": metric_value(report, ("validation_metrics", "brier_score"), ("brier_score",)),
        "holdout_2026_accuracy": metric_value(report, ("holdout_2026_metrics", "accuracy")),
        "holdout_2026_log_loss": metric_value(report, ("holdout_2026_metrics", "log_loss")),
        "holdout_2026_brier_score": metric_value(report, ("holdout_2026_metrics", "brier_score")),
        "baseline_home_team_accuracy": metric_value(report, ("validation_metrics", "baseline_home_team_accuracy"), ("baseline_home_team_accuracy",)),
        "warnings": [warning for warning in report.get("warnings", []) if isinstance(warning, str)],
    }


def recommendation_from_deltas(
    validation_log_loss_delta: float | None,
    validation_brier_delta: float | None,
    validation_accuracy_delta: float | None,
    holdout_log_loss_delta: float | None,
    holdout_brier_delta: float | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if validation_log_loss_delta is None or validation_brier_delta is None:
        return "needs_more_data", ["Validation metrics are incomplete."]

    if validation_log_loss_delta < -0.003 or validation_brier_delta < -0.002:
        reasons.append("Pitcher model underperformed baseline on calibration-sensitive validation metrics.")
        return "keep_baseline", reasons

    if holdout_log_loss_delta is not None and holdout_brier_delta is not None:
        if holdout_log_loss_delta < -0.003 or holdout_brier_delta < -0.002:
            reasons.append("Holdout 2026 performance did not beat the baseline cleanly.")
            return "keep_baseline", reasons

    if validation_log_loss_delta >= 0.005 and validation_brier_delta >= 0.002 and (validation_accuracy_delta is None or validation_accuracy_delta >= -0.01):
        if holdout_log_loss_delta is None or holdout_brier_delta is None:
            reasons.append("Validation improved, but holdout comparison is incomplete.")
            return "needs_more_data", reasons
        if holdout_log_loss_delta >= 0.0 and holdout_brier_delta >= 0.0:
            reasons.append("Pitcher features improved validation and holdout calibration metrics enough to become a research-only candidate.")
            return "candidate_pitcher_model", reasons
        reasons.append("Validation improved, but holdout gains were mixed.")
        return "needs_more_data", reasons

    reasons.append("Pitcher features may help, but the lift is too small or mixed to switch models yet.")
    return "needs_more_data", reasons


def pitcher_feature_count(feature_columns: list[str]) -> int:
    return sum(1 for column in feature_columns if "pitcher" in column.lower())


def missing_pitcher_feature_rows(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if normalize_text(row.get("pitcher_data_quality")) == "missing")


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - train_pitcher_model")
    print("Training a pitcher-enhanced moneyline model for research-only comparison. No live picks, odds, ROI, CLV, calibration mapping, Telegram alerts, or real-money behavior will be created.")

    rows = load_rows()
    if not rows:
        print("No pitcher feature file found. No model was trained.")
        print("Next: run python mlb-engine/scripts/build_pitcher_features.py after the baseline moneyline feature dataset exists.")
        return

    warnings: list[str] = []
    baseline_warnings: list[str] = []
    baseline_report = load_json(BASELINE_REPORT_INPUT)
    if baseline_report is None:
        baseline_warnings.append("Baseline moneyline training report unavailable; comparison will be limited.")

    feature_columns = choose_feature_columns(rows, warnings)
    train_rows, validation_rows, holdout_rows, split_warnings = split_rows(rows)
    warnings.extend(split_warnings)

    if not feature_columns:
        print("No usable pre-game numeric feature columns found. No pitcher model was trained.")
        return
    if not train_rows:
        print("No 2023/2024 training rows found. No pitcher model was trained.")
        return
    if not validation_rows:
        print("No 2025 validation rows found. No pitcher model was trained.")
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
        warnings.append("scikit-learn is not installed; used ASTRODDS stdlib logistic regression fallback. Install scikit-learn later for comparable training: python -m pip install scikit-learn")
        weights, intercept = train_stdlib_logistic_regression(train_matrix, train_y)
        model = None
        model_type = "stdlib_logistic_regression"

    train_probabilities = model_probabilities(model, model_type, train_matrix, weights, intercept)
    validation_probabilities = model_probabilities(model, model_type, validation_matrix, weights, intercept)
    holdout_probabilities = model_probabilities(model, model_type, holdout_matrix, weights, intercept) if holdout_rows else []

    train_metrics = evaluate(train_y, train_probabilities)
    validation_metrics = evaluate(validation_y, validation_probabilities)
    holdout_metrics = evaluate(holdout_y, holdout_probabilities) if holdout_rows else {"accuracy": None, "log_loss": None, "brier_score": None, "baseline_home_team_accuracy": None}

    model_report = {
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
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "holdout_2026_metrics": holdout_metrics if holdout_rows else None,
        "validation_accuracy": validation_metrics["accuracy"],
        "validation_log_loss": validation_metrics["log_loss"],
        "validation_brier_score": validation_metrics["brier_score"],
        "holdout_2026_accuracy": holdout_metrics["accuracy"],
        "holdout_2026_log_loss": holdout_metrics["log_loss"],
        "holdout_2026_brier_score": holdout_metrics["brier_score"],
        "baseline_home_team_accuracy": validation_metrics["baseline_home_team_accuracy"],
        "feature_columns": feature_columns,
        "feature_count": len(feature_columns),
        "pitcher_feature_count": pitcher_feature_count(feature_columns),
        "missing_pitcher_feature_rows": missing_pitcher_feature_rows(rows),
        "excluded_columns": sorted(LEAKAGE_COLUMNS | PITCHER_TEXT_COLUMNS),
        "derived_pitcher_features": DERIVED_PITCHER_FEATURE_COLUMNS,
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
        "created_at": model_report["generated_at"],
        "official_pick_override": False,
        "research_only": True,
    }

    feature_payload = {
        "model_version": MODEL_VERSION,
        "feature_columns": feature_columns,
        "excluded_columns": sorted(LEAKAGE_COLUMNS | PITCHER_TEXT_COLUMNS),
        "derived_pitcher_features": DERIVED_PITCHER_FEATURE_COLUMNS,
        "imputation_values": preprocessor["imputation"],
        "scaling_means": preprocessor["means"],
        "scaling_stds": preprocessor["stds"],
        "target": "target_home_win",
        "market": "moneyline",
        "runline_enabled": False,
        "research_only": True,
    }

    write_json(MODEL_OUTPUT, model_payload)
    write_json(FEATURE_COLUMNS_OUTPUT, feature_payload)
    write_json(REPORT_OUTPUT, model_report)

    baseline_summary = summary_from_training_report(baseline_report or {})
    pitcher_summary = summary_from_training_report(model_report)

    validation_accuracy_delta = None
    validation_log_loss_delta = None
    validation_brier_delta = None
    holdout_accuracy_delta = None
    holdout_log_loss_delta = None
    holdout_brier_delta = None

    if baseline_report:
        baseline_validation_accuracy = baseline_summary["validation_accuracy"]
        baseline_validation_log_loss = baseline_summary["validation_log_loss"]
        baseline_validation_brier = baseline_summary["validation_brier_score"]
        baseline_holdout_accuracy = baseline_summary["holdout_2026_accuracy"]
        baseline_holdout_log_loss = baseline_summary["holdout_2026_log_loss"]
        baseline_holdout_brier = baseline_summary["holdout_2026_brier_score"]

        if baseline_validation_accuracy is not None and pitcher_summary["validation_accuracy"] is not None:
            validation_accuracy_delta = pitcher_summary["validation_accuracy"] - baseline_validation_accuracy
        if baseline_validation_log_loss is not None and pitcher_summary["validation_log_loss"] is not None:
            validation_log_loss_delta = baseline_validation_log_loss - pitcher_summary["validation_log_loss"]
        if baseline_validation_brier is not None and pitcher_summary["validation_brier_score"] is not None:
            validation_brier_delta = baseline_validation_brier - pitcher_summary["validation_brier_score"]

        if baseline_holdout_accuracy is not None and pitcher_summary["holdout_2026_accuracy"] is not None:
            holdout_accuracy_delta = pitcher_summary["holdout_2026_accuracy"] - baseline_holdout_accuracy
        if baseline_holdout_log_loss is not None and pitcher_summary["holdout_2026_log_loss"] is not None:
            holdout_log_loss_delta = baseline_holdout_log_loss - pitcher_summary["holdout_2026_log_loss"]
        if baseline_holdout_brier is not None and pitcher_summary["holdout_2026_brier_score"] is not None:
            holdout_brier_delta = baseline_holdout_brier - pitcher_summary["holdout_2026_brier_score"]

    recommendation, recommendation_reasons = recommendation_from_deltas(
        validation_log_loss_delta,
        validation_brier_delta,
        validation_accuracy_delta,
        holdout_log_loss_delta,
        holdout_brier_delta,
    )

    comparison_report = {
        "model_family": "moneyline",
        "delta_convention": "positive_is_better",
        "generated_at": model_report["generated_at"],
        "baseline_model": {
            "model_version": baseline_summary["model_version"],
            "model_type": baseline_summary["model_type"],
            "train_rows": baseline_summary["train_rows"],
            "validation_rows": baseline_summary["validation_rows"],
            "holdout_2026_rows": baseline_summary["holdout_2026_rows"],
            "validation_accuracy": baseline_summary["validation_accuracy"],
            "validation_log_loss": baseline_summary["validation_log_loss"],
            "validation_brier_score": baseline_summary["validation_brier_score"],
            "holdout_2026_accuracy": baseline_summary["holdout_2026_accuracy"],
            "holdout_2026_log_loss": baseline_summary["holdout_2026_log_loss"],
            "holdout_2026_brier_score": baseline_summary["holdout_2026_brier_score"],
            "baseline_home_team_accuracy": baseline_summary["baseline_home_team_accuracy"],
        },
        "pitcher_model": {
            "model_version": pitcher_summary["model_version"],
            "model_type": pitcher_summary["model_type"],
            "train_rows": pitcher_summary["train_rows"],
            "validation_rows": pitcher_summary["validation_rows"],
            "holdout_2026_rows": pitcher_summary["holdout_2026_rows"],
            "validation_accuracy": pitcher_summary["validation_accuracy"],
            "validation_log_loss": pitcher_summary["validation_log_loss"],
            "validation_brier_score": pitcher_summary["validation_brier_score"],
            "holdout_2026_accuracy": pitcher_summary["holdout_2026_accuracy"],
            "holdout_2026_log_loss": pitcher_summary["holdout_2026_log_loss"],
            "holdout_2026_brier_score": pitcher_summary["holdout_2026_brier_score"],
            "baseline_home_team_accuracy": pitcher_summary["baseline_home_team_accuracy"],
            "feature_count": model_report["feature_count"],
            "pitcher_feature_count": model_report["pitcher_feature_count"],
            "missing_pitcher_feature_rows": model_report["missing_pitcher_feature_rows"],
        },
        "accuracy_delta": rounded(validation_accuracy_delta),
        "log_loss_delta": rounded(validation_log_loss_delta),
        "brier_score_delta": rounded(validation_brier_delta),
        "holdout_accuracy_delta": rounded(holdout_accuracy_delta),
        "holdout_log_loss_delta": rounded(holdout_log_loss_delta),
        "holdout_brier_score_delta": rounded(holdout_brier_delta),
        "recommendation": recommendation,
        "reasons": recommendation_reasons,
        "warnings": [
            *warnings,
            *baseline_warnings,
            "Pitcher model comparison is research only and does not switch the active prediction path.",
            "No official picks, Strong Buys, ROI, CLV, or calibration mapping were created.",
        ],
    }

    write_json(COMPARISON_OUTPUT, comparison_report)

    print("Pitcher model training completed.")
    print(f"- model type: {model_type}")
    print(f"- train rows: {len(train_rows)}")
    print(f"- validation rows: {len(validation_rows)}")
    print(f"- holdout 2026 rows: {len(holdout_rows)}")
    print(f"- validation accuracy: {model_report['validation_accuracy']}")
    print(f"- validation log_loss: {model_report['validation_log_loss']}")
    print(f"- validation brier_score: {model_report['validation_brier_score']}")
    print(f"- holdout 2026 accuracy: {model_report['holdout_2026_accuracy']}")
    print(f"- holdout 2026 log_loss: {model_report['holdout_2026_log_loss']}")
    print(f"- holdout 2026 brier_score: {model_report['holdout_2026_brier_score']}")
    print(f"- model artifact: {MODEL_OUTPUT}")
    print(f"- feature columns: {FEATURE_COLUMNS_OUTPUT}")
    print(f"- training report: {REPORT_OUTPUT}")
    print(f"- comparison report: {COMPARISON_OUTPUT}")
    print(f"- recommendation: {recommendation}")
    for reason in recommendation_reasons:
        print(f"Reason: {reason}")
    for warning in warnings + baseline_warnings:
        print(f"Warning: {warning}")
    print("No today_predictions.json file was created. Active baseline predictions remain unchanged.")


if __name__ == "__main__":
    main()
