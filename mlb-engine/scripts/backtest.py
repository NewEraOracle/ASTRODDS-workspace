"""Backtest scaffold for ASTRODDS MLB Engine.

Never reports fake ROI, CLV, win rate, or edge. It only runs once verified
historical predictions and settled results are available.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - backtest")
    prediction_files = list(PROCESSED_DIR.glob("*prediction*.*"))
    result_files = list(PROCESSED_DIR.glob("*result*.*"))
    if not prediction_files or not result_files:
        print("Backtest skipped. Verified historical predictions and settled results are both required.")
        print("No fake ROI, CLV, win rate, or calibration was produced.")
        print("Next: generate historical model predictions and join them to settled MLB outcomes.")
        return
    print("Backtest inputs detected, but backtest logic is not implemented yet.")
    print("No performance report was written.")


if __name__ == "__main__":
    main()