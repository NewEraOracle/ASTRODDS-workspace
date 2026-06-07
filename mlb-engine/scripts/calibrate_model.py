"""Calibration scaffold for ASTRODDS MLB Engine.

Detects historical baseline predictions when present, but does not create fake
calibration quality. Calibration logic comes later.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ENGINE_ROOT / "models"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
HISTORICAL_PREDICTIONS = PROCESSED_DIR / "moneyline_historical_predictions.csv"


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def has_model() -> bool:
    return (MODELS_DIR / "moneyline_baseline_model.pkl").exists()


def has_historical_predictions() -> bool:
    return HISTORICAL_PREDICTIONS.exists()


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - calibrate_model")
    if not has_model():
        print("No trained moneyline model artifact found. Calibration skipped.")
        print("Next: run train_model.py after verified features exist.")
        return
    if has_historical_predictions():
        print(f"Historical predictions detected: {HISTORICAL_PREDICTIONS}")
        print("Calibration logic is not implemented yet. No calibration artifact was written.")
        print("No fake calibration quality, confidence, edge, ROI, or CLV was created.")
        return
    print("No verified historical predictions found. Calibration skipped.")
    print("Next: run generate_historical_predictions.py to create moneyline_historical_predictions.csv.")


if __name__ == "__main__":
    main()