"""Write ASTRODDS Python MLB Engine readiness status.

This is a safety/reporting layer only. It does not create live picks,
today_predictions.json, ROI, CLV, market edge, profit, official picks, or real
money behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ENGINE_ROOT / "models"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"

TRAINING_REPORT = MODELS_DIR / "moneyline_training_report.json"
CALIBRATION_REPORT = CALIBRATION_DIR / "moneyline_calibration_report.json"
HISTORICAL_PREDICTIONS_REPORT = PROCESSED_DIR / "moneyline_historical_predictions_report.json"
MODEL_STATUS_OUTPUT = OUTPUTS_DIR / "model_status.json"
BLOCKING_CALIBRATION_QUALITIES = {"weak", "missing", "not_enough_history"}


def ensure_dirs() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def number_value(payload: dict[str, Any] | None, key: str) -> int | float | None:
    if not payload:
        return None
    value = payload.get(key)
    return value if isinstance(value, (int, float)) else None


def string_value(payload: dict[str, Any] | None, key: str, fallback = "") -> str:
    if not payload:
        return fallback
    value = payload.get(key)
    return value if isinstance(value, str) else fallback


def append_report_warnings(warnings: list[str], report: dict[str, Any] | None) -> None:
    if not report:
        return
    report_warnings = report.get("warnings")
    if isinstance(report_warnings, list):
        for warning in report_warnings:
            if isinstance(warning, str) and warning not in warnings:
                warnings.append(warning)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - model_status")
    print("Writing model readiness status only. No live picks, ROI, CLV, edge, profit, or today_predictions.json will be created.")

    training = load_json(TRAINING_REPORT)
    calibration = load_json(CALIBRATION_REPORT)
    historical = load_json(HISTORICAL_PREDICTIONS_REPORT)
    warnings: list[str] = []
    block_reasons: list[str] = []

    model_available = training is not None
    calibration_quality = string_value(calibration, "calibration_quality", "missing")
    calibrated_probability_mapping_available = False
    market_prices_connected = False

    if not model_available:
        block_reasons.append("No trained baseline moneyline model report found")
    if calibration_quality in BLOCKING_CALIBRATION_QUALITIES:
        block_reasons.append(f"Calibration quality is {calibration_quality}")
    if calibration is None:
        block_reasons.append("No calibration report found")
    if not market_prices_connected:
        block_reasons.append("No market prices connected")
    if not calibrated_probability_mapping_available:
        block_reasons.append("No calibrated probability mapping available")

    if historical is None:
        warnings.append("Historical predictions report is missing; run generate_historical_predictions.py for full status context.")
    append_report_warnings(warnings, training)
    append_report_warnings(warnings, calibration)
    append_report_warnings(warnings, historical)
    warnings.append("Python baseline model is exposed for status only; it cannot create official ASTRODDS picks yet.")
    warnings.append("total_runs remains future secondary; runline remains disabled.")

    official_pick_eligible = False
    status = {
        "engineAvailable": True,
        "modelAvailable": model_available,
        "modelVersion": string_value(training, "model_version", string_value(calibration, "model_version", "unknown")),
        "modelType": string_value(training, "model_type", string_value(calibration, "model_type", "unknown")),
        "trainingRows": number_value(training, "train_rows"),
        "validationRows": number_value(training, "validation_rows"),
        "holdout2026Rows": number_value(training, "holdout_2026_rows"),
        "validationAccuracy": number_value(training, "accuracy"),
        "baselineHomeTeamAccuracy": number_value(training, "baseline_home_team_accuracy"),
        "brierScore": number_value(calibration, "brier_score"),
        "logLoss": number_value(calibration, "log_loss"),
        "expectedCalibrationError": number_value(calibration, "expected_calibration_error"),
        "maxCalibrationError": number_value(calibration, "max_calibration_error"),
        "calibrationQuality": calibration_quality,
        "supportedMarkets": ["moneyline"],
        "disabledMarkets": ["runline"],
        "officialPickEligible": official_pick_eligible,
        "officialPickBlockReasons": list(dict.fromkeys(block_reasons)),
        "warnings": list(dict.fromkeys(warnings)),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

    with MODEL_STATUS_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(status, file, ensure_ascii=False, indent=2)

    print("Model status written.")
    print(f"- output: {MODEL_STATUS_OUTPUT}")
    print(f"- model available: {status['modelAvailable']}")
    print(f"- calibration quality: {status['calibrationQuality']}")
    print(f"- official pick eligible: {status['officialPickEligible']}")
    for reason in status["officialPickBlockReasons"]:
        print(f"Block: {reason}")


if __name__ == "__main__":
    main()