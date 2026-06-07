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

## Fetch Real MLB Schedule/Results Data

Use the public MLB StatsAPI schedule endpoint to fetch regular-season games by year:

```bash
python mlb-engine/scripts/fetch_data.py --year 2023
python mlb-engine/scripts/fetch_data.py --year 2024
python mlb-engine/scripts/fetch_data.py --year 2025
python mlb-engine/scripts/fetch_data.py --year 2026
```

Each successful run creates:

```text
mlb-engine/data/raw/mlb_schedule_<YEAR>.json
mlb-engine/data/processed/mlb_games_<YEAR>.csv
```

The processed CSV is moneyline-ready source data and includes:

- `game_id`
- `game_date`
- `season`
- `game_type`
- `status`
- `home_team`
- `away_team`
- `home_score`
- `away_score`
- `winner`
- `home_win`
- `away_win`
- `venue`
- `doubleheader`
- `game_number`

If a game is scheduled, future, incomplete, or missing final scores, the row is kept but result fields remain empty. Results are never faked.

2026 is season-to-date/live paper calibration data only. It should not be treated as a completed full-season training set.

## Build Moneyline Features

After fetching yearly game files, build the first supervised Moneyline/Game Winner feature dataset:

```bash
python mlb-engine/scripts/build_features.py
```

This creates:

```text
mlb-engine/data/processed/mlb_moneyline_features.csv
mlb-engine/data/processed/mlb_moneyline_features_report.json
```

`mlb_moneyline_features.csv` contains one row per completed game with a known winner. The target column is:

```text
target_home_win
```

`target_home_win` is `1` when the home team won and `0` when the away team won. It is for future supervised Moneyline model training only.

Feature rules:

- Uses only games before the current game.
- Resets team history by season.
- Keeps 2026 completed games, but treats 2026 as season-to-date.
- Skips scheduled/incomplete games as labeled training rows.
- Uses `0.5` win-percentage defaults only when a team has no prior games.
- Leaves rest/run fields empty when there is no prior history rather than faking values.

This is feature building only. It is not model training, not calibration, not backtesting, and not a prediction engine.

## Other Commands

```bash
python mlb-engine/scripts/train_model.py
python mlb-engine/scripts/calibrate_model.py
python mlb-engine/scripts/backtest.py
python mlb-engine/scripts/predict_today.py
```

These scripts still exit cleanly and print next steps when required data/model artifacts are missing. This is not a trained model yet.

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