"""Backtest scaffold for ASTRODDS MLB Engine.

Detects historical baseline predictions, but never reports fake ROI, CLV, win
rate, profit, or betting edge without verified market prices/odds.
"""
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
HISTORICAL_PREDICTIONS = PROCESSED_DIR / "moneyline_historical_predictions.csv"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - backtest")
    if not HISTORICAL_PREDICTIONS.exists():
        print("Backtest skipped. Verified historical model predictions are required.")
        print("No fake ROI, CLV, win rate, profit, or calibration was produced.")
        print("Next: run generate_historical_predictions.py.")
        return
    print(f"Historical predictions detected: {HISTORICAL_PREDICTIONS}")
    print("Backtest ROI is still skipped because verified market odds/Polymarket prices are not connected yet.")
    print("No fake ROI, CLV, win rate, profit, edge, or performance report was written.")


if __name__ == "__main__":
    main()