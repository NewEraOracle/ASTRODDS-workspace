from pathlib import Path
import csv
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mlb_schedule_results_2016_2026.csv"
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

def pct(wins, games):
    return wins / games if games else None

def main():
    with DATA.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    completed = [
        r for r in rows
        if r.get("winner") and r.get("home_win") not in ("", None)
    ]

    completed.sort(key=lambda r: (r["official_date"], r["game_id"]))

    pitcher_history = {}
    tested = 0
    correct = 0
    skipped = 0

    min_prior_starts = 5

    for g in completed:
        away_team = g["away_team"]
        home_team = g["home_team"]
        winner = g["winner"]

        away_pitcher = g.get("away_probable_pitcher", "").strip()
        home_pitcher = g.get("home_probable_pitcher", "").strip()

        away_key = away_pitcher
        home_key = home_pitcher

        away_hist = pitcher_history.get(away_key)
        home_hist = pitcher_history.get(home_key)

        if (
            not away_pitcher or
            not home_pitcher or
            not away_hist or
            not home_hist or
            away_hist["starts"] < min_prior_starts or
            home_hist["starts"] < min_prior_starts
        ):
            skipped += 1
        else:
            away_rate = pct(away_hist["wins"], away_hist["starts"])
            home_rate = pct(home_hist["wins"], home_hist["starts"])

            pick = home_team if home_rate >= away_rate else away_team

            tested += 1
            if pick == winner:
                correct += 1

        # update pitcher history after game
        if away_pitcher:
            pitcher_history.setdefault(away_key, {"starts": 0, "wins": 0})
            pitcher_history[away_key]["starts"] += 1
            if winner == away_team:
                pitcher_history[away_key]["wins"] += 1

        if home_pitcher:
            pitcher_history.setdefault(home_key, {"starts": 0, "wins": 0})
            pitcher_history[home_key]["starts"] += 1
            if winner == home_team:
                pitcher_history[home_key]["wins"] += 1

    accuracy = round((correct / tested) * 100, 2) if tested else 0

    report = f"""ASTRODDS STARTING PITCHER BASELINE

Dataset:
2016-2026 completed MLB games

Rule:
Pick the team whose probable starting pitcher has the better historical team-win rate in prior starts.
Minimum prior starts required: {min_prior_starts}

Results:
Tested games: {tested}
Correct: {correct}
Skipped: {skipped}
Starting pitcher baseline accuracy: {accuracy}%

Comparison:
Home team baseline: 53.21%
Recent 10-game form: 53.86%
Previous season record: 55.10%
70% previous season + 30% recent form: 55.66%

Conclusion:
{"Starting pitcher history improves the baseline." if accuracy > 55.66 else "Starting pitcher history alone does not beat the current combined team-strength baseline."}

Next:
Test combined formula:
Team strength + recent form + pitcher advantage
"""

    out = REPORTS / "starting_pitcher_baseline_report.txt"
    out.write_text(report, encoding="utf-8")

    print(report)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
