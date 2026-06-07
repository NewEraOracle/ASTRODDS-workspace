# ASTRODDS MLB Engine

This is the optional Python foundation for future ASTRODDS MLB modeling. It is separate from the existing Next.js dashboard, scanner, Decision Center, Telegram, paper trading, and safety gates.

The engine is intentionally safe today:

- No paid APIs are required.
- No fake picks are created.
- No fake ROI, CLV, win rate, confidence, or calibration is reported.
- `predict_today.py` does not write `outputs/today_predictions.json` until real model artifacts and verified today features exist.
- Run Line is disabled for now because useful Polymarket availability is low or missing.

## Market Priority

1. Moneyline / Game Winner: primary.
2. Over/Under / Total Runs: secondary and higher variance.
3. Run Line: disabled/ignored for now.

## Data Plan

Future model data should cover 2023, 2024, 2025, and 2026 season-to-date. Treat 2026 as live/paper calibration data, not a completed full training season.

## Commands

```bash
python mlb-engine/scripts/fetch_data.py
python mlb-engine/scripts/build_features.py
python mlb-engine/scripts/train_model.py
python mlb-engine/scripts/calibrate_model.py
python mlb-engine/scripts/backtest.py
python mlb-engine/scripts/predict_today.py
```

Each script exits cleanly and prints next steps if required data is missing.

## Prediction Export Contract

When real predictions are available, export them to:

```text
mlb-engine/outputs/today_predictions.json
```

Only these market types are active:

- `moneyline`
- `total_runs`

If `runline` appears, the TypeScript loader ignores it and reports a warning.

Real-money trading remains OFF. Paper mode remains ON.