from pathlib import Path
import csv
import json
import time
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2016, 2027))

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

def safe_get(obj, path, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def game_row(game, season):
    status = safe_get(game, ["status", "abstractGameState"], "")
    detailed_state = safe_get(game, ["status", "detailedState"], "")

    away_team = safe_get(game, ["teams", "away", "team", "name"], "")
    home_team = safe_get(game, ["teams", "home", "team", "name"], "")

    away_score = safe_get(game, ["teams", "away", "score"], None)
    home_score = safe_get(game, ["teams", "home", "score"], None)

    away_pitcher = safe_get(game, ["teams", "away", "probablePitcher", "fullName"], "")
    home_pitcher = safe_get(game, ["teams", "home", "probablePitcher", "fullName"], "")

    winner = ""
    home_win = ""

    if away_score is not None and home_score is not None and status == "Final":
        if home_score > away_score:
            winner = home_team
            home_win = 1
        elif away_score > home_score:
            winner = away_team
            home_win = 0

    return {
        "season": season,
        "game_id": game.get("gamePk"),
        "game_date": game.get("gameDate"),
        "official_date": game.get("officialDate"),
        "status": status,
        "detailed_state": detailed_state,
        "away_team": away_team,
        "home_team": home_team,
        "away_score": away_score,
        "home_score": home_score,
        "winner": winner,
        "home_win": home_win,
        "away_probable_pitcher": away_pitcher,
        "home_probable_pitcher": home_pitcher,
    }

def main():
    all_rows = []
    report = {
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "years": {},
    }

    for year in YEARS:
        print(f"Fetching MLB schedule {year}...")

        url = (
            "https://statsapi.mlb.com/api/v1/schedule"
            f"?sportId=1&season={year}&gameType=R"
            "&hydrate=probablePitcher,team,linescore"
        )

        data = fetch_json(url)

        raw_path = RAW / f"mlb_schedule_{year}.json"
        raw_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        rows = []
        for date_block in data.get("dates", []):
            for game in date_block.get("games", []):
                rows.append(game_row(game, year))

        year_csv = PROCESSED / f"mlb_schedule_results_{year}.csv"

        if rows:
            with year_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        completed = [r for r in rows if r["status"] == "Final" and r["winner"]]
        all_rows.extend(rows)

        report["years"][str(year)] = {
            "games": len(rows),
            "completed": len(completed),
            "rawPath": str(raw_path),
            "csvPath": str(year_csv),
        }

        print(f"  games={len(rows)} completed={len(completed)}")
        time.sleep(0.4)

    combined_path = PROCESSED / "mlb_schedule_results_2016_2026.csv"

    if all_rows:
        with combined_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    report["combinedCsv"] = str(combined_path)

    report_path = REPORTS / "schedule_results_fetch_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("")
    print("DONE")
    print(f"Combined CSV: {combined_path}")
    print(f"Report:       {report_path}")

if __name__ == "__main__":
    main()
