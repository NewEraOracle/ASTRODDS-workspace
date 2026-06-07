"""Training scaffold for ASTRODDS MLB Engine.

Moneyline is the primary future target. total_runs is secondary. runline is
intentionally disabled for now.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
FEATURE_PATTERNS = ("*features*.csv", "*features*.json", "*training*.csv", "*training*.json")


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def find_feature_files() -> list[Path]:
    files: list[Path] = []
    for pattern in FEATURE_PATTERNS:
        files.extend(PROCESSED_DIR.glob(pattern))
    return sorted(set(files))


def main() -> None:
    ensure_dirs()
    feature_files = find_feature_files()
    print("ASTRODDS MLB Engine - train_model")
    if not feature_files:
        print("No processed training features found. No model was trained.")
        print("Next: build verified features from historical 2023-2025 data and keep 2026 as season-to-date paper calibration.")
        return
    print(f"Found {len(feature_files)} candidate feature file(s).")
    print("Training is not implemented yet. No model artifact was written.")
    print("Next: train a calibrated moneyline model before enabling total_runs experiments.")


if __name__ == "__main__":
    main()