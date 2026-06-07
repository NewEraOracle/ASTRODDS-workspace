# ASTRODDS 12/10 MLB Engine Plan

ASTRODDS already has a working scanner-first base. This plan adds an optional Python MLB Engine beside the current app without replacing the existing TypeScript/Next.js safety system.

## Current Base Stays

The existing ASTRODDS app remains responsible for:

- `/astrodds` dashboard and Decision Center
- `/astrodss` redirect
- Unified signals API
- Scanner diagnostics API
- Official Picks, Strong Buys, Watchlist, Why No Bet, Data Quality, Lineup Impact, and Whale Bonus separation
- Telegram configuration and safety checks
- Paper trading and paper resolver
- Whale intelligence as a bonus-only layer
- Real-money trading OFF

No Python output should override official pick thresholds until calibration, data quality, and market safety are proven.

## TypeScript vs Python Split

TypeScript/Next.js remains the production control plane:

- UI and dashboard state
- API routes
- Decision Center
- Telegram status and alert routing
- Paper tracking
- Safety gates
- Official pick guardrails

Python becomes the optional research and modeling engine:

- MLB data ingestion
- Feature engineering
- Model training
- Calibration
- Backtesting
- Prediction export to `mlb-engine/outputs/today_predictions.json`

If the Python export file is missing or invalid, ASTRODDS continues with the current system.

## Research Reference

The BaseballPred notebooks, including `BP10_Model_w_Lineup.ipynb`, are research inspiration only. Do not copy notebook code directly into production. Production modules must be typed, validated, testable, and safe to run when data is missing.

## Historical Data Plan

The future model should use verified MLB data from:

- 2023
- 2024
- 2025
- 2026 season-to-date

Treat 2026 carefully as live/paper calibration data, not as a completed full-season training set.

## Market Priority

1. Moneyline / Game Winner is primary.
2. Over/Under / Total Runs is secondary and higher variance.
3. Run Line is disabled for now because Polymarket availability is currently low or not useful enough.

## Future Official Pick Requirements

Official MLB picks should eventually require:

- Positive calibrated edge
- Reliable data quality
- Pitcher reliability
- Lineup reliability
- Valid market price
- Valid order book/liquidity
- Conservative risk controls

A high model probability alone is not enough. A strong team can still be a bad bet if the market price is too expensive.

## Calibration Rules

The Python engine must not invent calibration quality. Allowed calibration quality values are:

- `strong`
- `medium`
- `weak`
- `not_enough_history`
- `missing`

If history is insufficient, the engine must say so and avoid fake confidence.

## Whale Layer

Whales remain bonus-only. Whale support can confirm a good model signal, but it cannot create an official MLB pick by itself and cannot override bad data, bad order book, stale entry, or negative edge.

## Safety Principle

Real-money trading stays OFF. Paper mode stays ON.

No bet is better than fake confidence.