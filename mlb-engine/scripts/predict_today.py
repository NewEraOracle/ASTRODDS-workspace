"""Export safe research-only MLB moneyline predictions for today's games.

This loads real today feature rows and the baseline moneyline model. It writes
outputs/today_predictions.json for diagnostics/watchlist use only. It does not
create official picks, market prices, edge, ROI, CLV, Telegram alerts, or real
money behavior.
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
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
TODAY_FEATURES_PATH = PROCESSED_DIR / "mlb_today_features.csv"
MODEL_PATH = MODELS_DIR / "moneyline_baseline_model.pkl"
FEATURE_COLUMNS_PATH = MODELS_DIR / "moneyline_feature_columns.json"
MODEL_STATUS_PATH = OUTPUTS_DIR / "model_status.json"
PREDICTION_PATH = OUTPUTS_DIR / "today_predictions.json"
CALIBRATION_MAPPING_PATH = CALIBRATION_DIR / "moneyline_calibration_mapping.json"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)


def remove_stale_prediction_file() -> None:
    try:
        if PREDICTION_PATH.exists():
            PREDICTION_PATH.unlink()
    except OSError as error:
        print(f"Warning: unable to remove stale today_predictions.json safely: {error}")


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


def parse_int(value: str | int | float | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def load_calibration_mapping(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    mapping = load_json(path)
    if mapping is None:
        return None, ["Calibration mapping unavailable"]
    bins = mapping.get("bins")
    if not isinstance(bins, list) or not bins:
        return mapping, ["Calibration mapping unavailable: no populated bins"]
    warnings = string_list(mapping.get("warnings"))
    if mapping.get("mappingStatus") == "research_only":
        warnings.append("Calibration mapping is research-only")
    if mapping.get("officialUseAllowed") is not False:
        warnings.append("Calibration mapping official-use flag is not safely false; official use remains blocked")
    return mapping, dedupe(warnings)


def calibration_bin_for_probability(probability: float, mapping: dict[str, Any] | None) -> dict[str, Any] | None:
    if mapping is None:
        return None
    raw_bins = mapping.get("bins")
    if not isinstance(raw_bins, list):
        return None
    valid_bins = [item for item in raw_bins if isinstance(item, dict)]
    for index, item in enumerate(valid_bins):
        lower = parse_float(item.get("binLower"))
        upper = parse_float(item.get("binUpper"))
        actual_rate = parse_float(item.get("actualHomeWinRate"))
        count = parse_int(item.get("count"))
        if lower is None or upper is None or actual_rate is None or count is None or count <= 0:
            continue
        is_last = index == len(valid_bins) - 1
        if lower <= probability < upper or (is_last and lower <= probability <= upper):
            return item
    return None


def apply_calibration_mapping(
    probability: float,
    mapping: dict[str, Any] | None,
    mapping_load_warnings: list[str],
) -> tuple[float | None, str, str | None, int | None, list[str]]:
    if mapping is None:
        return None, "missing", None, None, dedupe(mapping_load_warnings + ["Calibration mapping unavailable"])
    mapping_status = str(mapping.get("mappingStatus") or "missing")
    method = str(mapping.get("method") or "unavailable")
    bin_row = calibration_bin_for_probability(probability, mapping)
    warnings = mapping_load_warnings[:]
    if bin_row is None:
        warnings.append("Calibration mapping unavailable for this raw probability bin")
        return None, mapping_status, method, None, dedupe(warnings)
    calibrated_probability = parse_float(bin_row.get("actualHomeWinRate"))
    count = parse_int(bin_row.get("count"))
    if calibrated_probability is None:
        warnings.append("Calibration mapping bin missing observed home win rate")
        return None, mapping_status, method, count, dedupe(warnings)
    return round(calibrated_probability, 6), mapping_status, method, count, dedupe(warnings)

def load_model(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as file:
            payload = pickle.load(file)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except ModuleNotFoundError as error:
        print(f"Model load skipped. Missing package needed for pickled model: {error.name}")
        return None
    except Exception as error:
        print(f"Model load skipped safely: {error}")
        return None


def load_feature_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def sigmoid(value: float) -> float:
    if value >= 35:
        return 1.0 - 1e-15
    if value <= -35:
        return 1e-15
    return 1 / (1 + math.exp(-value))


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


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def split_warning_string(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def prediction_for_row(
    row: dict[str, str],
    probability: float,
    model_payload: dict[str, Any],
    model_status: dict[str, Any],
    calibration_mapping: dict[str, Any] | None,
    calibration_mapping_warnings: list[str],
    generated_at: str,
) -> dict[str, Any]:
    calibration_quality = str(model_status.get("calibrationQuality") or "missing")
    model_version = str(model_payload.get("model_version") or model_status.get("modelVersion") or "unknown")
    model_type = str(model_payload.get("model_type") or model_status.get("modelType") or "unknown")
    block_reasons = string_list(model_status.get("officialPickBlockReasons"))
    calibrated_probability, calibration_mapping_status, calibration_method, calibration_sample_size, mapping_warnings = apply_calibration_mapping(
        probability,
        calibration_mapping,
        calibration_mapping_warnings,
    )
    calibration_warnings = dedupe(string_list(model_status.get("warnings")) + mapping_warnings)
    row_warnings = split_warning_string(row.get("missing_data_warnings"))

    reasons = [
        "Baseline moneyline model generated a raw home-win probability from pre-game historical team features.",
        "Market price not connected for this prediction.",
    ]
    if calibrated_probability is None:
        reasons.append("Calibration mapping unavailable for this prediction.")
    else:
        reasons.append("Calibration mapping applied from historical bins for research only.")

    if calibration_quality == "weak":
        reasons.append("Calibration weak - research only.")
    elif calibration_quality in {"missing", "not_enough_history"}:
        reasons.append(f"Calibration {calibration_quality} - research only.")

    mapping_block_reason = "Calibration mapping is research-only" if calibrated_probability is not None else "No calibrated probability mapping available"
    official_edge_block_reasons = dedupe(
        block_reasons
        + [
            "No market price connected for this prediction",
            mapping_block_reason,
            "Raw and calibrated model probabilities are not official betting edge",
            "Python today predictions are diagnostics/watchlist only",
        ]
    )

    calibration_risk = "Calibration mapping is research-only and weak; official use remains blocked." if calibrated_probability is not None else "Calibration mapping unavailable."

    return {
        "gameId": row.get("game_id") or "",
        "date": row.get("game_date") or "",
        "sport": "MLB",
        "league": "MLB",
        "homeTeam": row.get("home_team") or "",
        "awayTeam": row.get("away_team") or "",
        "marketType": "moneyline",
        "marketAvailability": "unknown",
        "pick": "research_only",
        "rawModelProbability": round(probability, 6),
        "calibratedProbability": calibrated_probability,
        "marketProbability": None,
        "rawEdge": None,
        "calibratedEdge": None,
        "confidence": None,
        "dataQuality": row.get("data_quality") or "unknown",
        "calibrationQuality": calibration_quality,
        "calibrationMethod": calibration_method,
        "calibrationSampleSize": calibration_sample_size,
        "calibrationMappingStatus": calibration_mapping_status,
        "calibrationWarnings": calibration_warnings,
        "lineupStatus": "missing",
        "pitcherStatus": "missing",
        "bullpenStatus": "missing",
        "weatherImpact": "unknown",
        "officialDecision": "research_only",
        "officialPickEligible": False,
        "officialEdgeAllowed": False,
        "officialEdgeBlockReasons": official_edge_block_reasons,
        "reasons": dedupe(reasons),
        "risks": dedupe(row_warnings + [
            "No verified market price or Polymarket probability is attached.",
            "Lineups, pitcher details, bullpen status, and weather are missing in the Python today export.",
            calibration_risk,
            "Weak or missing calibration blocks official use.",
        ]),
        "isPaperOnly": True,
        "modelVersion": model_version,
        "modelType": model_type,
        "generatedAt": generated_at,
    }


def write_predictions(payload: dict[str, Any]) -> None:
    with PREDICTION_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - predict_today")
    print("Exporting research-only baseline moneyline predictions. No official picks, odds, edge, ROI, CLV, Telegram, or real-money behavior will be created.")

    feature_config = load_json(FEATURE_COLUMNS_PATH)
    model_status = load_json(MODEL_STATUS_PATH) or {}
    model_payload = load_model(MODEL_PATH)
    rows = load_feature_rows(TODAY_FEATURES_PATH)
    calibration_mapping, calibration_mapping_warnings = load_calibration_mapping(CALIBRATION_MAPPING_PATH)

    if feature_config is None:
        remove_stale_prediction_file()
        print(f"Missing or invalid feature column file: {FEATURE_COLUMNS_PATH}")
        print("No today_predictions.json file was written.")
        return
    if model_payload is None:
        remove_stale_prediction_file()
        print(f"Missing or invalid model file: {MODEL_PATH}")
        print("No today_predictions.json file was written.")
        return
    if not rows:
        remove_stale_prediction_file()
        print(f"Missing or empty today feature file: {TODAY_FEATURES_PATH}")
        print("Run python mlb-engine/scripts/build_today_features.py first. No today_predictions.json file was written.")
        return

    feature_columns = feature_config.get("feature_columns")
    if not isinstance(feature_columns, list) or not all(isinstance(column, str) for column in feature_columns):
        remove_stale_prediction_file()
        print("Feature column file does not contain a valid feature_columns list.")
        print("No today_predictions.json file was written.")
        return

    generated_at = datetime.now(timezone.utc).isoformat()
    predictions: list[dict[str, Any]] = []
    skipped_rows = 0
    warnings: list[str] = []

    for row in rows:
        probability = model_probability(model_payload, transform_row(row, feature_columns, feature_config))
        if probability is None:
            skipped_rows += 1
            continue
        predictions.append(prediction_for_row(row, probability, model_payload, model_status, calibration_mapping, calibration_mapping_warnings, generated_at))

    if skipped_rows:
        warnings.append(f"Skipped {skipped_rows} today feature rows with unavailable model probability.")
    warnings.extend(calibration_mapping_warnings[:3])
    if calibration_mapping is None:
        warnings.append("Calibration mapping unavailable")
    else:
        warnings.append(f"Calibration mapping status: {calibration_mapping.get('mappingStatus', 'missing')} - research-only diagnostics")
    warnings.extend([
        "Today predictions are research-only diagnostics and cannot create official ASTRODDS picks.",
        "No market prices, official edge, ROI, CLV, Telegram alerts, or real-money behavior were created.",
    ])

    payload = {
        "generatedAt": generated_at,
        "sourceFeatureFile": str(TODAY_FEATURES_PATH),
        "modelPath": str(MODEL_PATH),
        "modelStatusPath": str(MODEL_STATUS_PATH),
        "calibrationMappingPath": str(CALIBRATION_MAPPING_PATH),
        "calibrationMappingStatus": str(calibration_mapping.get("mappingStatus") if calibration_mapping else "missing"),
        "predictionPolicy": "research_only_watchlist_diagnostics",
        "officialPickOverride": False,
        "officialPickEligible": False,
        "isPaperOnly": True,
        "marketTypes": ["moneyline"],
        "disabledMarkets": ["runline"],
        "predictionCount": len(predictions),
        "warnings": warnings,
        "predictions": predictions,
    }
    write_predictions(payload)

    print("Today predictions exported safely.")
    print(f"- prediction count: {len(predictions)}")
    print(f"- output JSON: {PREDICTION_PATH}")
    print("Official picks remain blocked. Real-money trading remains OFF.")
    for warning in warnings:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()