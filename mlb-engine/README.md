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

The processed CSV is moneyline-ready source data and includes game id, date, teams, final score fields, winner fields, venue, and schedule metadata.

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

## Train Baseline Moneyline Model

Train the first baseline Moneyline/Game Winner model:

```bash
python mlb-engine/scripts/train_model.py
```

Training policy:

- Trains only on 2023 and 2024 rows.
- Validates/tests on 2025 rows.
- Keeps completed 2026 rows as season-to-date holdout/paper evaluation only.
- Uses only pre-game numeric features.
- Excludes leakage fields such as `game_id`, `game_date`, final scores, `winner`, and `target_home_win` from model inputs.
- Uses Logistic Regression with scikit-learn when available.
- Falls back to a small stdlib logistic-regression baseline if scikit-learn is not installed.

Training creates:

```text
mlb-engine/models/moneyline_baseline_model.pkl
mlb-engine/models/moneyline_feature_columns.json
mlb-engine/models/moneyline_training_report.json
```

This is a baseline Moneyline model only. It is not calibrated yet. Betting edge requires a market price or Polymarket implied probability later. Model probability alone is not a bet.

The training report contains model metrics only, such as validation accuracy, log loss, Brier score, and home-team baseline accuracy. It does not report ROI, CLV, profit, or betting performance.

## Train Pitcher-Enhanced Comparison Model

After the pitcher feature layer is built, evaluate whether it improves the baseline Moneyline model:

```bash
python mlb-engine/scripts/train_pitcher_model.py
```

This creates:

```text
mlb-engine/models/moneyline_pitcher_model.pkl
mlb-engine/models/moneyline_pitcher_feature_columns.json
mlb-engine/models/moneyline_pitcher_training_report.json
mlb-engine/models/moneyline_model_comparison_report.json
```

This step is research only. It compares the pitcher-enhanced model against the current baseline and reports honest validation / holdout deltas. It does not switch the active model used by `predict_today.py`, and it does not create official picks, live betting outputs, ROI, CLV, or calibration mapping for live use.


## Generate Historical Model Predictions

After training the baseline moneyline model, score historical feature rows for calibration/backtest preparation:

```bash
python mlb-engine/scripts/generate_historical_predictions.py
```

This creates:

```text
mlb-engine/data/processed/moneyline_historical_predictions.csv
mlb-engine/data/processed/moneyline_historical_predictions_report.json
```

Historical prediction rows include:

- `game_id`
- `game_date`
- `season`
- `home_team`
- `away_team`
- `target_home_win`
- `raw_home_win_probability`
- `predicted_home_win`
- `split`
- `model_version`
- `model_type`
- `generated_at`

Split policy:

- 2023 and 2024: `train`
- 2025: `validation`
- completed 2026: `holdout_2026`

This step does not create live picks, official picks, betting edge, ROI, CLV, confidence, calibration, Polymarket probabilities, or `today_predictions.json`.

## Measure Baseline Calibration

After generating historical predictions, measure raw model probability calibration:

```bash
python mlb-engine/scripts/calibrate_model.py
```

This creates:

```text
mlb-engine/calibration/moneyline_calibration_report.json
mlb-engine/calibration/moneyline_calibration_bins.csv
```

The bins CSV groups historical predictions into probability ranges and reports:

- `bin_lower`
- `bin_upper`
- `count`
- `average_predicted_probability`
- `actual_home_win_rate`
- `calibration_error`

The report JSON includes Brier score, log loss, expected calibration error, max calibration error, rows by split, model metadata, calibration quality, and warnings.

Calibration quality is conservative and can be:

- `strong`
- `medium`
- `weak`
- `not_enough_history`
- `missing`

This is probability calibration measurement only. It is not betting ROI, not CLV, not market edge, not an official pick, and not a live signal. Betting ROI and edge require market prices or Polymarket implied probabilities later.

## Build Today Moneyline Features

Build safe research-only feature rows for today or the next scheduled MLB date found in the latest 2026 processed schedule:

```bash
python mlb-engine/scripts/build_today_features.py
```

This creates:

```text
mlb-engine/data/processed/mlb_today_features.csv
mlb-engine/data/processed/mlb_today_features_report.json
```

Today feature rows:

- use only completed games before each scheduled game;
- leave current-game result, winner, and target fields empty;
- use the same baseline moneyline feature columns where possible;
- use `0.5` win-percentage defaults only when no prior team history exists;
- report missing lineup, pitcher, bullpen, and weather data as warnings instead of faking them.

## Build Starting Pitcher Features

Build a safe starting-pitcher feature foundation for future Moneyline retraining:

```bash
python mlb-engine/scripts/build_pitcher_features.py
```

This creates:

```text
mlb-engine/data/processed/mlb_pitcher_features.csv
mlb-engine/data/processed/mlb_pitcher_features_report.json
```

If the baseline `mlb_moneyline_features.csv` exists, the pitcher builder also creates an optional merged research file:

```text
mlb-engine/data/processed/mlb_moneyline_features_with_pitchers.csv
```

Pitcher feature rules:

- Uses only completed games.
- Builds trailing pitcher-history features only from prior starts.
- Leaves pitcher fields blank when data is missing rather than faking them.
- Falls back to a safe year-level MLB StatsAPI schedule hydrate with `probablePitcher` if the saved raw schedule snapshot does not already include pitcher fields.
- Remains feature-only and does not train, calibrate, or score a production model.

## Build Bullpen Fatigue Features

Build a research-only bullpen fatigue feature layer from the public MLB schedule snapshots:

```bash
python mlb-engine/scripts/build_bullpen_features.py
```

This creates:

```text
mlb-engine/data/processed/mlb_bullpen_features.csv
mlb-engine/data/processed/mlb_bullpen_features_report.json
mlb-engine/data/processed/mlb_moneyline_features_with_bullpen.csv
mlb-engine/data/processed/mlb_moneyline_features_with_pitchers_bullpen.csv
```

The bullpen layer uses public linescore snapshots and recent-game stress proxies to approximate late-inning bullpen workload. It is research-only, approximate, and fail-soft:

- no picks are created;
- no official picks are changed;
- no ROI, CLV, confidence, or calibration is invented;
- no real-money behavior is enabled.

If bullpen data is missing, the report marks the layer as missing or partial and keeps the output safe.

## Export Research-Only Today Predictions

After building today features and model status, export safe baseline Moneyline diagnostics:

```bash
python mlb-engine/scripts/predict_today.py
```

This creates `mlb-engine/outputs/today_predictions.json` only when valid today features and model artifacts exist.

The exported predictions are research-only/watchlist diagnostics:

- raw model probability is included;
- calibrated probability remains `null` until a real calibration mapping exists;
- market probability and edge remain `null` until a real market price is matched;
- confidence remains `null`;
- official use is blocked;
- real-money trading remains OFF;
- Telegram alerts are not sent;
- no official ASTRODDS picks or Strong Buys are created.

## Other Commands

```bash
python mlb-engine/scripts/calibrate_model.py
python mlb-engine/scripts/backtest.py
python mlb-engine/scripts/predict_today.py
```

These scripts still exit cleanly and print next steps when required data/model artifacts are missing. Calibration, backtesting, and prediction export come later.

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
