"""
ASTRODDS BaseballPred-inspired historical dataset builder.

Phase 1 goal:
Create a clean historical MLB moneyline modeling dataset skeleton from 2016-current.

This script is intentionally safe:
- no betting
- no live decisions
- no dashboard changes
- no API loops
"""

from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

YEARS = list(range(2016, 2027))

FEATURE_GROUPS = [
    "schedule_result",
    "starting_pitcher",
    "bullpen",
    "batting_lineup",
    "weather_park",
    "sportsbook_odds",
    "market_probability",
    "model_target",
]

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    manifest = {
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "years": YEARS,
        "featureGroups": FEATURE_GROUPS,
        "nextSteps": [
            "fetch MLB schedule/results per year",
            "attach probable/starting pitchers",
            "attach pitcher season/recent stats",
            "attach bullpen fatigue features",
            "attach batting/team offensive features",
            "attach weather/park features",
            "attach sportsbook odds snapshots where available",
            "train/test by season",
            "evaluate edge buckets and ROI",
        ],
    }

    manifest_path = REPORTS / "historical_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    skeleton_path = PROCESSED / "mlb_moneyline_dataset_skeleton.csv"
    columns = [
        "game_date",
        "season",
        "game_id",
        "away_team",
        "home_team",
        "winner",
        "selected_side",
        "home_win",
        "away_starting_pitcher",
        "home_starting_pitcher",
        "away_pitcher_era",
        "home_pitcher_era",
        "away_bullpen_fatigue",
        "home_bullpen_fatigue",
        "away_recent_runs",
        "home_recent_runs",
        "temperature",
        "wind_speed",
        "precipitation",
        "park_factor",
        "sportsbook_home_prob",
        "sportsbook_away_prob",
        "model_home_prob",
        "model_away_prob",
        "edge",
    ]

    with skeleton_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

    print("Created:")
    print(manifest_path)
    print(skeleton_path)
    print("")
    print("Next: fetch MLB schedule/results 2016-current.")

if __name__ == "__main__":
    main()
