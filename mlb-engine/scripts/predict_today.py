"""Prediction export scaffold for ASTRODDS MLB Engine.

Exports today_predictions.json only when real model artifacts and verified today
features exist. It does not create fake picks.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
PREDICTION_PATH = OUTPUTS_DIR / "today_predictions.json"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def has_model() -> bool:
    return any(path.is_file() for path in MODELS_DIR.glob("*"))


def has_today_features() -> bool:
    return any(PROCESSED_DIR.glob("*today*features*.*"))


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - predict_today")
    if not has_model():
        print("No trained model artifact found. No today_predictions.json file was written.")
        print("Next: train and calibrate a moneyline model from verified historical data.")
        return
    if not has_today_features():
        print("No verified today feature file found. No today_predictions.json file was written.")
        print("Next: build today's real MLB features before exporting predictions.")
        return
    print("Prediction inputs detected, but prediction export logic is not implemented yet.")
    print(f"No prediction file was written at {PREDICTION_PATH}.")


if __name__ == "__main__":
    main()