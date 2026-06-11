"""Train a research-only modern-window ASTRODDS moneyline model.

This script trains a separate baseline moneyline/game-winner model on the
expanded 2016-2026 historical feature dataset. It is comparison-only:

- no live picks are created;
- no today_predictions.json file is written;
- no official ASTRODDS pick behavior changes;
- no Telegram or real-money behavior changes.
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

FEATURE_INPUT = PROCESSED_DIR / "mlb_moneyline_features_2016_2026.csv"
BASELINE_REPORT_INPUT = MODELS_DIR / "moneyline_training_report.json"
EXPANSION_REPORT_INPUT = PROCESSED_DIR / "mlb_historical_expansion_2016_2026_report.json"

MODEL_OUTPUT = MODELS_DIR / "moneyline_modern_2016_2026_model.pkl"
FEATURE_COLUMNS_OUTPUT = MODELS_DIR / "moneyline_modern_2016_2026_feature_columns.json"
REPORT_OUTPUT = MODELS_DIR / "moneyline_modern_2016_2026_training_report.json"
COMPARISON_OUTPUT = MODELS_DIR / "moneyline_modern_window_comparison_report.json"

MODEL_VERSION = "moneyline_modern_2016_2026_v0.1"
DEFAULT_TRAIN_SEASONS = set(range(2016, 2024))
DEFAULT_VALIDATION_SEASONS = {2024, 2025}
DEFAULT_HOLDOUT_SEASONS = {2026}
COMPARISON_VALIDATION_SEASONS = {2025}

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


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


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


def choose_feature_columns(rows: list[dict[str, str]], train_rows: list[dict[str, str]], warnings: list[str]) -> list[str]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    candidates = [column for column in columns if column not in LEAKAGE_COLUMNS]
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
    return usable


def resolve_season_windows(rows: list[dict[str, str]], warnings: list[str]) -> tuple[set[int], set[int], set[int], str]:
    seasons = sorted({season for season in (parse_int(row.get("season")) for row in rows) if season is not None})
    if DEFAULT_TRAIN_SEASONS.issubset(seasons) and DEFAULT_VALIDATION_SEASONS.issubset(seasons) and DEFAULT_HOLDOUT_SEASONS.issubset(seasons):
        return DEFAULT_TRAIN_SEASONS, DEFAULT_VALIDATION_SEASONS, DEFAULT_HOLDOUT_SEASONS, "default_2016_2023_train_2024_2025_validation_2026_holdout"

    if len(seasons) >= 4:
        holdout = {seasons[-1]}
        validation = set(seasons[-3:-1])
        train = set(seasons[:-3])
        warnings.append(
            "Default modern-window split was unavailable; used safest chronological fallback "
            f"train={sorted(train)}, validation={sorted(validation)}, holdout={sorted(holdout)}."
        )
        return train, validation, holdout, "fallback_chronological"

    warnings.append("Not enough distinct seasons were available for the requested modern-window split.")
    return set(), set(), set(), "insufficient_seasons"


def split_rows(
    rows: list[dict[str, str]],
    train_seasons: set[int],
    validation_seasons: set[int],
    holdout_seasons: set[int],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    train: list[dict[str, str]] = []
    validation: list[dict[str, str]] = []
    validation_comparison: list[dict[str, str]] = []
    holdout: list[dict[str, str]] = []
    skipped = 0

    for row in rows:
        season = parse_int(row.get("season"))
        target = parse_int(row.get("target_home_win"))
        if season is None or target not in {0, 1}:
            skipped += 1
            continue
        if season in train_seasons:
            train.append(row)
        elif season in validation_seasons:
            validation.append(row)
        elif season in holdout_seasons:
            holdout.append(row)

        if season in COMPARISON_VALIDATION_SEASONS:
            validation_comparison.append(row)

    if skipped:
        warnings.append(f"Skipped {skipped} rows with missing season or target_home_win.")
    return train, validation, validation_comparison, holdout, warnings


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


def try_sklearn_train(train_matrix: list[list[float]], train_y: list[int]) -> tuple[Any, str] | None:
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def recommendation_from_deltas(
    validation_log_loss_delta: float | None,
    validation_brier_delta: float | None,
    holdout_log_loss_delta: float | None,
    holdout_brier_delta: float | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if validation_log_loss_delta is None or validation_brier_delta is None:
        return "needs_more_data", ["Comparison metrics are incomplete."]

    if validation_log_loss_delta <= -0.003 or validation_brier_delta <= -0.002:
        reasons.append("Modern 2016-2026 candidate underperformed the current baseline on common 2025 comparison metrics.")
        return "keep_current_baseline", reasons

    if holdout_log_loss_delta is not None and holdout_brier_delta is not None:
        if holdout_log_loss_delta <= -0.003 or holdout_brier_delta <= -0.002:
            reasons.append("Modern 2016-2026 candidate did not preserve holdout 2026 calibration quality.")
            return "keep_current_baseline", reasons

    if validation_log_loss_delta >= 0.004 and validation_brier_delta >= 0.0015:
        if holdout_log_loss_delta is None or holdout_brier_delta is None:
            reasons.append("Common-window validation improved, but 2026 holdout evidence is incomplete.")
            return "needs_more_data", reasons
        if holdout_log_loss_delta >= 0.0 and holdout_brier_delta >= 0.0:
            reasons.append("Modern 2016-2026 candidate improved common-window validation and did not regress on 2026 holdout metrics.")
            return "candidate_modern_2016_2026", reasons
        reasons.append("Modern 2016-2026 candidate improved 2025 comparison metrics, but 2026 holdout gains were mixed.")
        return "needs_more_data", reasons

    reasons.append("Modern 2016-2026 candidate does not yet show enough calibration lift to replace the current baseline.")
    return "needs_more_data", reasons


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - train_modern_window_model")
    print("Training a research-only 2016-2026 moneyline comparison model. No live picks, official picks, today_predictions.json, Telegram changes, or real-money behavior will be created.")

    rows = load_rows()
    if not rows:
        print("No expanded 2016-2026 moneyline feature file found. No modern-window model was trained.")
        print("Next: run python mlb-engine/scripts/build_features.py --start-year 2016 --end-year 2026")
        return

    warnings: list[str] = []
    baseline_warnings: list[str] = []
    baseline_report = load_json(BASELINE_REPORT_INPUT)
    expansion_report = load_json(EXPANSION_REPORT_INPUT)
    if baseline_report is None:
        baseline_warnings.append("Current baseline training report unavailable; comparison will be limited.")
    if expansion_report is None:
        warnings.append("Historical expansion report unavailable; training will continue using the expanded feature CSV only.")

    train_seasons, validation_seasons, holdout_seasons, split_policy = resolve_season_windows(rows, warnings)
    train_rows, validation_rows, validation_comparison_rows, holdout_rows, split_warnings = split_rows(rows, train_seasons, validation_seasons, holdout_seasons)
    warnings.extend(split_warnings)

    if not train_rows:
        print("No modern-window training rows found. No modern-window model was trained.")
        return
    if not validation_rows:
        print("No modern-window validation rows found. No modern-window model was trained.")
        return
    if not validation_comparison_rows:
        warnings.append("No 2025 comparison rows were available; baseline comparison will be limited.")

    feature_columns = choose_feature_columns(rows, train_rows, warnings)
    if not feature_columns:
        print("No usable pre-game numeric feature columns found. No modern-window model was trained.")
        return

    preprocessor = fit_preprocessor(train_rows, feature_columns)
    train_matrix = transform_rows(train_rows, feature_columns, preprocessor)
    validation_matrix = transform_rows(validation_rows, feature_columns, preprocessor)
    comparison_validation_matrix = transform_rows(validation_comparison_rows, feature_columns, preprocessor)
    holdout_matrix = transform_rows(holdout_rows, feature_columns, preprocessor)
    train_y = targets(train_rows)
    validation_y = targets(validation_rows)
    comparison_validation_y = targets(validation_comparison_rows)
    holdout_y = targets(holdout_rows)

    sklearn_model = try_sklearn_train(train_matrix, train_y)
    weights: list[float] = []
    intercept = 0.0
    if sklearn_model is not None:
        model, model_type = sklearn_model
    else:
        warnings.append(
            "scikit-learn is not installed; used ASTRODDS stdlib logistic regression fallback. "
            "Install scikit-learn later for comparable production training: python -m pip install scikit-learn"
        )
        weights, intercept = train_stdlib_logistic_regression(train_matrix, train_y)
        model = None
        model_type = "stdlib_logistic_regression"

    train_probabilities = model_probabilities(model, model_type, train_matrix, weights, intercept)
    validation_probabilities = model_probabilities(model, model_type, validation_matrix, weights, intercept)
    comparison_validation_probabilities = model_probabilities(model, model_type, comparison_validation_matrix, weights, intercept) if validation_comparison_rows else []
    holdout_probabilities = model_probabilities(model, model_type, holdout_matrix, weights, intercept) if holdout_rows else []

    train_metrics = evaluate(train_y, train_probabilities)
    validation_metrics = evaluate(validation_y, validation_probabilities)
    comparison_validation_metrics = evaluate(comparison_validation_y, comparison_validation_probabilities) if validation_comparison_rows else None
    holdout_metrics = evaluate(holdout_y, holdout_probabilities) if holdout_rows else None

    generated_at = datetime.now(timezone.utc).isoformat()
    training_report = {
        "model_version": MODEL_VERSION,
        "model_type": model_type,
        "generated_at": generated_at,
        "target": "target_home_win",
        "market": "moneyline",
        "training_window": "2016-2023",
        "validation_window": "2024-2025",
        "holdout_2026_policy": "completed 2026 rows are held out as season-to-date/paper evaluation only; they are not used for training",
        "split_policy": split_policy,
        "train_seasons": sorted(train_seasons),
        "validation_seasons": sorted(validation_seasons),
        "holdout_seasons": sorted(holdout_seasons),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "holdout_2026_rows": len(holdout_rows),
        "comparison_validation_2025_rows": len(validation_comparison_rows),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "comparison_validation_2025_metrics": comparison_validation_metrics,
        "holdout_2026_metrics": holdout_metrics,
        "accuracy": validation_metrics["accuracy"],
        "log_loss": validation_metrics["log_loss"],
        "brier_score": validation_metrics["brier_score"],
        "baseline_home_team_accuracy": validation_metrics["baseline_home_team_accuracy"],
        "feature_columns": feature_columns,
        "excluded_columns": sorted(LEAKAGE_COLUMNS),
        "historical_window": expansion_report.get("historical_window") if isinstance(expansion_report, dict) else "2016-2026",
        "historical_completed_games": expansion_report.get("completed_games_used") if isinstance(expansion_report, dict) else None,
        "warnings": warnings,
        "research_only": True,
        "active_model_changed": False,
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
        "created_at": generated_at,
        "official_pick_override": False,
        "research_only": True,
        "training_window": "2016-2023",
        "validation_window": "2024-2025",
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
        "research_only": True,
        "training_window": "2016-2023",
        "validation_window": "2024-2025",
    }

    baseline_summary = summary_from_training_report(baseline_report or {})
    modern_validation_accuracy = comparison_validation_metrics["accuracy"] if comparison_validation_metrics else None
    modern_validation_log_loss = comparison_validation_metrics["log_loss"] if comparison_validation_metrics else None
    modern_validation_brier_score = comparison_validation_metrics["brier_score"] if comparison_validation_metrics else None
    modern_holdout_accuracy = holdout_metrics["accuracy"] if holdout_metrics else None
    modern_holdout_log_loss = holdout_metrics["log_loss"] if holdout_metrics else None
    modern_holdout_brier_score = holdout_metrics["brier_score"] if holdout_metrics else None

    baseline_validation_accuracy = baseline_summary["validation_accuracy"]
    baseline_validation_log_loss = baseline_summary["validation_log_loss"]
    baseline_validation_brier_score = baseline_summary["validation_brier_score"]
    baseline_holdout_accuracy = baseline_summary["holdout_2026_accuracy"]
    baseline_holdout_log_loss = baseline_summary["holdout_2026_log_loss"]
    baseline_holdout_brier_score = baseline_summary["holdout_2026_brier_score"]

    accuracy_delta = rounded(modern_validation_accuracy - baseline_validation_accuracy) if baseline_validation_accuracy is not None and modern_validation_accuracy is not None else None
    log_loss_delta = rounded(baseline_validation_log_loss - modern_validation_log_loss) if baseline_validation_log_loss is not None and modern_validation_log_loss is not None else None
    brier_score_delta = rounded(baseline_validation_brier_score - modern_validation_brier_score) if baseline_validation_brier_score is not None and modern_validation_brier_score is not None else None
    holdout_accuracy_delta = rounded(modern_holdout_accuracy - baseline_holdout_accuracy) if baseline_holdout_accuracy is not None and modern_holdout_accuracy is not None else None
    holdout_log_loss_delta = rounded(baseline_holdout_log_loss - modern_holdout_log_loss) if baseline_holdout_log_loss is not None and modern_holdout_log_loss is not None else None
    holdout_brier_score_delta = rounded(baseline_holdout_brier_score - modern_holdout_brier_score) if baseline_holdout_brier_score is not None and modern_holdout_brier_score is not None else None

    recommendation, recommendation_reasons = recommendation_from_deltas(
        log_loss_delta,
        brier_score_delta,
        holdout_log_loss_delta,
        holdout_brier_score_delta,
    )

    comparison_report = {
        "model_family": "moneyline",
        "comparison_type": "modern_window_2016_2026_vs_current_baseline",
        "delta_convention": "positive_is_better",
        "generated_at": generated_at,
        "active_model_changed": False,
        "baseline_model": {
            "model_version": baseline_summary["model_version"],
            "model_type": baseline_summary["model_type"],
            "training_window": "2023-2024",
            "comparison_validation_window": "2025",
            "holdout_window": "2026",
            "train_rows": baseline_summary["train_rows"],
            "validation_rows": baseline_summary["validation_rows"],
            "holdout_2026_rows": baseline_summary["holdout_2026_rows"],
            "validation_accuracy": baseline_validation_accuracy,
            "validation_log_loss": baseline_validation_log_loss,
            "validation_brier_score": baseline_validation_brier_score,
            "holdout_2026_accuracy": baseline_holdout_accuracy,
            "holdout_2026_log_loss": baseline_holdout_log_loss,
            "holdout_2026_brier_score": baseline_holdout_brier_score,
            "baseline_home_team_accuracy": baseline_summary["baseline_home_team_accuracy"],
        },
        "modern_model": {
            "model_version": MODEL_VERSION,
            "model_type": model_type,
            "training_window": "2016-2023",
            "research_validation_window": "2024-2025",
            "comparison_validation_window": "2025",
            "holdout_window": "2026",
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "holdout_2026_rows": len(holdout_rows),
            "validation_accuracy": modern_validation_accuracy,
            "validation_log_loss": modern_validation_log_loss,
            "validation_brier_score": modern_validation_brier_score,
            "holdout_2026_accuracy": modern_holdout_accuracy,
            "holdout_2026_log_loss": modern_holdout_log_loss,
            "holdout_2026_brier_score": modern_holdout_brier_score,
            "baseline_home_team_accuracy": comparison_validation_metrics["baseline_home_team_accuracy"] if comparison_validation_metrics else None,
            "feature_count": len(feature_columns),
        },
        "accuracy_delta": accuracy_delta,
        "log_loss_delta": log_loss_delta,
        "brier_score_delta": brier_score_delta,
        "holdout_accuracy_delta": holdout_accuracy_delta,
        "holdout_log_loss_delta": holdout_log_loss_delta,
        "holdout_brier_score_delta": holdout_brier_score_delta,
        "recommendation": recommendation,
        "reasons": recommendation_reasons,
        "warnings": [
            *warnings,
            *baseline_warnings,
            "Modern-window comparison is research only and does not switch the active ASTRODDS model.",
            "Modern-window calibration and historical prediction generation still need their own dedicated pass before any active research promotion.",
            "No official picks, Strong Buys, Telegram picks, or real-money behavior were created.",
        ],
    }

    with MODEL_OUTPUT.open("wb") as file:
        pickle.dump(model_payload, file)
    write_json(FEATURE_COLUMNS_OUTPUT, feature_payload)
    write_json(REPORT_OUTPUT, training_report)
    write_json(COMPARISON_OUTPUT, comparison_report)

    print("Modern-window training completed.")
    print(f"- model type: {model_type}")
    print(f"- train rows: {len(train_rows)}")
    print(f"- validation rows (2024-2025): {len(validation_rows)}")
    print(f"- comparison validation rows (2025): {len(validation_comparison_rows)}")
    print(f"- holdout 2026 rows: {len(holdout_rows)}")
    print(f"- research validation accuracy: {training_report['accuracy']}")
    print(f"- research validation log_loss: {training_report['log_loss']}")
    print(f"- research validation brier_score: {training_report['brier_score']}")
    print(f"- common 2025 log_loss delta vs current baseline: {comparison_report['log_loss_delta']}")
    print(f"- common 2025 brier delta vs current baseline: {comparison_report['brier_score_delta']}")
    print(f"- 2026 holdout log_loss delta vs current baseline: {comparison_report['holdout_log_loss_delta']}")
    print(f"- 2026 holdout brier delta vs current baseline: {comparison_report['holdout_brier_score_delta']}")
    print(f"- model artifact: {MODEL_OUTPUT}")
    print(f"- feature columns: {FEATURE_COLUMNS_OUTPUT}")
    print(f"- training report: {REPORT_OUTPUT}")
    print(f"- comparison report: {COMPARISON_OUTPUT}")
    print(f"- recommendation: {recommendation}")
    for reason in recommendation_reasons:
        print(f"Reason: {reason}")
    for warning in warnings + baseline_warnings:
        print(f"Warning: {warning}")
    print("Active baseline model remains unchanged. No today_predictions.json file was created.")


if __name__ == "__main__":
    main()
