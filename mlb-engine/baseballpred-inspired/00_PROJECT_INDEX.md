# ASTRODDS MLB Moneyline Research Pipeline

ASTRODDS is built like BaseballPred:
data -> model -> backtest -> edge -> live snapshot -> resolve results -> improve features.

## Completed Pipeline

### 01 Fetch Schedule / Results: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/fetch_mlb_schedule_results.py

Output:
mlb-engine/baseballpred-inspired/data/processed/mlb_schedule_results_2016_2026.csv

Result:
23,826 completed MLB games from 2016-2026.

---

### 02 Clean Baseline Model: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/02_clean_baseline_model.py

Model:
mlb-engine/baseballpred-inspired/models/ASTRODDS_MLB_MONEYLINE_MODEL_V1.json

Formula:
60% previous season record
20% recent 10-game form
20% previous season Pythagorean strength

Backtest:
Overall accuracy: 56.01%
8%+ model gap bucket: 58.56%

---

### 03 Edge Ledger Report: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/03_edge_ledger_report.py

Purpose:
Reads edge-ledger.json and reports bucket performance.

---

### 04 Resolve Edge Results: READY
Script:
mlb-engine/baseballpred-inspired/scripts/04_resolve_edge_results.py

Purpose:
Converts pending picks to win/loss after games finish.

Current status:
Pending until games are final.

---

### 05 Live VVS Snapshot: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/05_live_vvs_snapshot.py

Purpose:
Captures live VVS picks and updates edge-ledger.json.

---

### 06 Feature Readiness Audit: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/06_feature_readiness_audit.py

Result:
Detected generic reasons and alias warnings.

Purpose:
Identify missing pitcher, bullpen, lineup, weather, injury context.

---

### 07 Clean VVS Reason Builder: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/07_clean_vvs_reason_builder.py

Outputs:
.astrodds/VVS-clean-final-latest.csv
.astrodds/VVS-clean-final-latest.json
public/astrodds-vvs-clean.html

Result:
Clean VVS board with alias warnings removed, one pick per game, and clean model reasons.

---

## Current Clean VVS Board

URL:
http://localhost:3000/astrodds-vvs-clean.html

Current clean VVS picks:
5

Mode:
Paper only

---

## Current VVS Rules

Moneyline only
Market probability 30%-75%
Edge 3%-25%
Model gap 8%+
Confidence high/medium
Risk not high/unknown
Max 10 picks
Do not force picks
Paper only

---

## Still Missing / Next Pipeline Steps

### 08 Historical Odds / Edge Evaluation
Needed:
opening odds
closing odds
closing line value
ROI by edge bucket
win rate by edge bucket

Status:
NOT BUILT

---

### 09 Pitching Features
Needed:
starting pitcher ERA
WHIP
strikeout rate
walk rate
recent starts
rest days
handedness

Status:
NOT BUILT

---

### 10 Bullpen Features
Needed:
bullpen innings last 1 / 3 / 7 days
reliever fatigue
closer availability
bullpen ERA / FIP if available

Status:
NOT BUILT

---

### 11 Lineup / Batter Features
Needed:
confirmed lineup
projected lineup
missing key hitters
offense vs pitcher handedness
recent team batting form

Status:
NOT BUILT

---

### 12 Weather / Park Features
Needed:
temperature
wind speed
wind direction
precipitation
stadium / park factor
dome/open roof status

Status:
NOT BUILT

---

### 13 Backend VVS Integration
Needed:
modelProbabilityGapPct
vvsEligible
vvsReason
vvsRank

Current status:
VVS filtering is done safely in snapshot scripts and public clean page.

Status:
PARTIAL

---

## Next Safe Commands After Games Finish

python ".\mlb-engine\baseballpred-inspired\scripts\04_resolve_edge_results.py"
python ".\mlb-engine\baseballpred-inspired\scripts\03_edge_ledger_report.py"

## Rule

Do not add real-money automation.
Paper only until edge buckets prove results.
Quality over quantity.

### 08 Game Context Snapshot: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/08_game_context_snapshot.py

Result:
Connected probable pitchers, lineups, venue, weather, and game status.

---

### 09 Pitcher Context Snapshot: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/09_pitcher_context_snapshot.py

Result:
Connected ERA, WHIP, innings, strikeouts, walks, and pitcher warning flags.

---

### 10 Bullpen Fatigue Snapshot: COMPLETE
Script:
mlb-engine/baseballpred-inspired/scripts/10_bullpen_fatigue_snapshot.py

Result:
Estimated bullpen fatigue using bullpen innings over 1 / 3 / 7 days.

---

### 11 Pro VVS Context Board: COMPLETE
Public page:
public/astrodds-vvs-pro-clean.html

Public data:
public/astrodds-vvs-pro-context.json

Result:
Clean VVS board with pitcher, lineup, weather, and bullpen context.

Status:
Paper/manual only. Context does not change picks yet.
