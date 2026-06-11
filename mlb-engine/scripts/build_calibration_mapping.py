"""Build a transparent research-only calibration mapping for MLB moneyline probabilities.

This reads the honest calibration bins produced by calibrate_model.py and maps
raw probability ranges to observed historical home win rates. It does not train a
new model, create live picks, calculate ROI/CLV/profit, or authorize official
ASTRODDS picks.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
BINS_PATH = CALIBRATION_DIR / "moneyline_calibration_bins.csv"
REPORT_PATH = CALIBRATION_DIR / "moneyline_calibration_report.json"
MAPPING_OUTPUT = CALIBRATION_DIR / "moneyline_calibration_mapping.json"


def ensure_dirs() -> None:
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)


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


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def load_bins(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return [], [f"Calibration bins file missing: {path}"]

    bins: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            lower = parse_float(row.get("bin_lower"))
            upper = parse_float(row.get("bin_upper"))
            count = parse_int(row.get("count"))
            average_probability = parse_float(row.get("average_predicted_probability"))
            actual_rate = parse_float(row.get("actual_home_win_rate"))
            calibration_error = parse_float(row.get("calibration_error"))
            if lower is None or upper is None or count is None:
                warnings.append(f"Calibration bin {index} skipped: invalid range or count.")
                continue
            if count <= 0 or average_probability is None or actual_rate is None or calibration_error is None:
                warnings.append(f"Calibration bin {index} skipped: no observed calibration data.")
                continue
            bins.append(
                {
                    "binLower": lower,
                    "binUpper": upper,
                    "averagePredictedProbability": average_probability,
                    "actualHomeWinRate": actual_rate,
                    "count": count,
                    "calibrationError": calibration_error,
                }
            )
    return bins, warnings


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def safe_round(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), 6)
    return None


def build_mapping() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    report = load_json(REPORT_PATH)
    bins, bin_warnings = load_bins(BINS_PATH)
    warnings = bin_warnings[:]

    if report is None:
        warnings.append(f"Calibration report missing or invalid: {REPORT_PATH}")
        report = {}

    calibration_quality = str(report.get("calibration_quality") or "missing")
    report_warnings = string_list(report.get("warnings"))
    warnings.extend(report_warnings)

    if calibration_quality == "weak":
        warnings.append("Calibration quality is weak - mapping is research-only")
    elif calibration_quality in {"missing", "not_enough_history"}:
        warnings.append(f"Calibration quality is {calibration_quality} - mapping is not official-use ready")

    if not bins:
        warnings.append("No populated calibration bins available; calibrated probabilities will remain unavailable.")

    mapping_status = "research_only" if bins else "missing"
    if calibration_quality in {"missing", "not_enough_history"}:
        mapping_status = "missing" if not bins else "research_only"

    return {
        "mappingStatus": mapping_status,
        "officialUseAllowed": False,
        "method": "bin_actual_home_win_rate_v1" if bins else "unavailable",
        "sourceBinsFile": str(BINS_PATH),
        "sourceReportFile": str(REPORT_PATH),
        "modelVersion": str(report.get("model_version") or "unknown"),
        "modelType": str(report.get("model_type") or "unknown"),
        "calibrationQuality": calibration_quality,
        "expectedCalibrationError": safe_round(report.get("expected_calibration_error")),
        "maxCalibrationError": safe_round(report.get("max_calibration_error")),
        "totalRows": report.get("total_rows") if isinstance(report.get("total_rows"), int) else None,
        "metricRows": report.get("metric_rows") if isinstance(report.get("metric_rows"), int) else None,
        "bins": bins,
        "warnings": dedupe(warnings),
        "generatedAt": generated_at,
    }


def write_mapping(mapping: dict[str, Any]) -> None:
    with MAPPING_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(mapping, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_calibration_mapping")
    print("Building transparent research-only moneyline probability mapping. No official picks, betting edge, ROI, CLV, Telegram, or real-money behavior will be created.")

    mapping = build_mapping()
    write_mapping(mapping)

    print("Calibration mapping completed safely.")
    print(f"- mapping status: {mapping['mappingStatus']}")
    print(f"- official use allowed: {mapping['officialUseAllowed']}")
    print(f"- bins: {len(mapping['bins'])}")
    print(f"- output JSON: {MAPPING_OUTPUT}")
    for warning in mapping["warnings"][:8]:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()