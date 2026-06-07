"""Backtest scaffold for ASTRODDS MLB Engine.

Detects historical predictions and calibration diagnostics, but never reports
fake ROI, CLV, win rate, profit, or betting edge without verified market prices.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"
HISTORICAL_PREDICTIONS = PROCESSED_DIR / "moneyline_historical_predictions.csv"
CALIBRATION_REPORT = CALIBRATION_DIR / "moneyline_calibration_report.json"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - backtest")
    if not HISTORICAL_PREDICTIONS.exists():
        print("Backtest skipped. Verified historical model predictions are required.")
        print("No fake ROI, CLV, win rate, profit, or calibration was produced.")
        print("Next: run generate_historical_predictions.py.")
        return
    print(f"Historical predictions detected: {HISTORICAL_PREDICTIONS}")
    if CALIBRATION_REPORT.exists():
        print(f"Calibration report detected: {CALIBRATION_REPORT}")
    else:
        print("No calibration report detected yet. Optional next step: run calibrate_model.py.")
    print("Backtest ROI is still skipped because verified market odds/Polymarket prices are not connected yet.")
    print("No fake ROI, CLV, win rate, profit, edge, or performance report was written.")


if __name__ == "__main__":
    main()