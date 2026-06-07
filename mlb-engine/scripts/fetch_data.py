"""Safe MLB data fetch scaffold for ASTRODDS.

This script intentionally avoids paid APIs and fake data. It prepares the local
engine folders and prints next steps until real public MLB data adapters are
wired in.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"

SEASONS = [2023, 2024, 2025, "2026 season-to-date"]


def ensure_dirs() -> None:
    for path in [RAW_DIR, PROCESSED_DIR, MODELS_DIR, OUTPUTS_DIR, CALIBRATION_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - fetch_data")
    print("Status: scaffold ready. No paid APIs required.")
    print("No fake MLB rows, odds, ROI, CLV, calibration, or picks were created.")
    print("Future data targets:")
    for season in SEASONS:
        print(f"- {season}")
    print("Next steps:")
    print("1. Add public MLB StatsAPI fetch adapters for schedules, teams, pitchers, and results.")
    print("2. Store raw verified data under mlb-engine/data/raw/.")
    print("3. Run build_features.py after raw data exists.")


if __name__ == "__main__":
    main()