"""Build real moneyline features for ASTRODDS MLB Engine.

Creates one supervised training row per completed MLB game using only team
history before that game. No model is trained here, and no predictions, ROI,
CLV, calibration, confidence, or win rate are created.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
FEATURE_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features.csv"
REPORT_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_report.json"
INPUT_PATTERN = "mlb_games_*.csv"
DEFAULT_START_YEAR = 2023
DEFAULT_END_YEAR = 2026

FEATURE_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "winner",
    "target_home_win",
    "home_games_played_before",
    "away_games_played_before",
    "home_wins_before",
    "away_wins_before",
    "home_losses_before",
    "away_losses_before",
    "home_win_pct_before",
    "away_win_pct_before",
    "home_last_10_win_pct",
    "away_last_10_win_pct",
    "home_last_30_win_pct",
    "away_last_30_win_pct",
    "home_runs_scored_last_10",
    "away_runs_scored_last_10",
    "home_runs_allowed_last_10",
    "away_runs_allowed_last_10",
    "home_run_diff_last_10",
    "away_run_diff_last_10",
    "home_runs_scored_last_30",
    "away_runs_scored_last_30",
    "home_runs_allowed_last_30",
    "away_runs_allowed_last_30",
    "home_run_diff_last_30",
    "away_run_diff_last_30",
    "home_rest_days",
    "away_rest_days",
    "home_back_to_back",
    "away_back_to_back",
    "win_pct_diff",
    "last_10_win_pct_diff",
    "last_30_win_pct_diff",
    "run_diff_last_10_diff",
    "run_diff_last_30_diff",
    "rest_days_diff",
]


@dataclass
class PriorGame:
    date: datetime
    runs_for: int
    runs_against: int
    won: bool


@dataclass
class TeamSeasonHistory:
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    recent_games: deque[PriorGame] = field(default_factory=deque)
    last_game_date: datetime | None = None

    def record_game(self, game_date: datetime, runs_for: int, runs_against: int) -> None:
        won = runs_for > runs_against
        self.games_played += 1
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.recent_games.append(PriorGame(date=game_date, runs_for=runs_for, runs_against=runs_against, won=won))
        while len(self.recent_games) > 30:
            self.recent_games.popleft()
        self.last_game_date = game_date


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build real moneyline features for ASTRODDS MLB Engine.")
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        choices=sorted(range(2016, 2027)),
        help="First MLB season year to include. Default: 2023.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=DEFAULT_END_YEAR,
        choices=sorted(range(2016, 2027)),
        help="Last MLB season year to include. Default: 2026.",
    )
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year.")
    return args


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def extract_year_from_path(path: Path) -> int | None:
    try:
        return int(path.stem.rsplit("_", 1)[-1])
    except ValueError:
        return None


def output_paths(start_year: int, end_year: int) -> tuple[Path, Path, Path | None]:
    if start_year == DEFAULT_START_YEAR and end_year == DEFAULT_END_YEAR:
        return FEATURE_OUTPUT, REPORT_OUTPUT, None

    suffix = f"_{start_year}_{end_year}"
    feature_output = PROCESSED_DIR / f"mlb_moneyline_features{suffix}.csv"
    report_output = PROCESSED_DIR / f"mlb_moneyline_features{suffix}_report.json"
    expansion_report_output = PROCESSED_DIR / f"mlb_historical_expansion{suffix}_report.json"
    return feature_output, report_output, expansion_report_output


def round_float(value: float | None) -> float | str:
    if value is None:
        return ""
    return round(value, 4)


def win_pct(wins: int, games: int) -> float:
    if games <= 0:
        return 0.5
    return wins / games


def recent_slice(history: TeamSeasonHistory, limit: int) -> list[PriorGame]:
    if limit <= 0:
        return []
    return list(history.recent_games)[-limit:]


def recent_win_pct(history: TeamSeasonHistory, limit: int) -> float:
    games = recent_slice(history, limit)
    if not games:
        return 0.5
    return sum(1 for game in games if game.won) / len(games)


def recent_runs_for(history: TeamSeasonHistory, limit: int) -> int | None:
    games = recent_slice(history, limit)
    if not games:
        return None
    return sum(game.runs_for for game in games)


def recent_runs_against(history: TeamSeasonHistory, limit: int) -> int | None:
    games = recent_slice(history, limit)
    if not games:
        return None
    return sum(game.runs_against for game in games)


def diff(left: float | int | None, right: float | int | None) -> float | int | None:
    if left is None or right is None:
        return None
    return left - right


def rest_days(history: TeamSeasonHistory, current_date: datetime) -> int | None:
    if history.last_game_date is None:
        return None
    return max(0, (current_date.date() - history.last_game_date.date()).days)


def back_to_back(rest: int | None) -> int | str:
    if rest is None:
        return ""
    return 1 if rest <= 1 else 0


def input_files(start_year: int, end_year: int) -> list[Path]:
    return sorted(
        path
        for path in PROCESSED_DIR.glob(INPUT_PATTERN)
        if path.name.startswith("mlb_games_")
        and path.name != FEATURE_OUTPUT.name
        and path.name != REPORT_OUTPUT.name
        and (year := extract_year_from_path(path)) is not None
        and start_year <= year <= end_year
    )


def read_games(files: list[Path]) -> tuple[list[dict[str, Any]], int, int]:
    games: list[dict[str, Any]] = []
    total_read = 0
    malformed = 0

    for file_path in files:
        with file_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                total_read += 1
                game_date = parse_date(row.get("game_date", ""))
                season = parse_int(row.get("season"))
                home_score = parse_int(row.get("home_score"))
                away_score = parse_int(row.get("away_score"))
                if game_date is None or season is None:
                    malformed += 1
                    continue
                row["_parsed_game_date"] = game_date
                row["_season_int"] = season
                row["_home_score_int"] = home_score
                row["_away_score_int"] = away_score
                games.append(row)

    games.sort(key=lambda row: (row["_parsed_game_date"], str(row.get("game_id") or "")))
    return games, total_read, malformed


def is_completed(row: dict[str, Any]) -> bool:
    return bool(row.get("winner")) and row.get("_home_score_int") is not None and row.get("_away_score_int") is not None


def history_key(season: int, team: str) -> tuple[int, str]:
    return season, team.strip().lower()


def get_history(histories: dict[tuple[int, str], TeamSeasonHistory], season: int, team: str) -> TeamSeasonHistory:
    key = history_key(season, team)
    if key not in histories:
        histories[key] = TeamSeasonHistory()
    return histories[key]


def build_feature_row(row: dict[str, Any], home_history: TeamSeasonHistory, away_history: TeamSeasonHistory) -> dict[str, Any]:
    home_team = str(row.get("home_team") or "")
    away_team = str(row.get("away_team") or "")
    home_score = row["_home_score_int"]
    away_score = row["_away_score_int"]
    game_date = row["_parsed_game_date"]
    home_rest = rest_days(home_history, game_date)
    away_rest = rest_days(away_history, game_date)

    home_win_pct = win_pct(home_history.wins, home_history.games_played)
    away_win_pct = win_pct(away_history.wins, away_history.games_played)
    home_last_10 = recent_win_pct(home_history, 10)
    away_last_10 = recent_win_pct(away_history, 10)
    home_last_30 = recent_win_pct(home_history, 30)
    away_last_30 = recent_win_pct(away_history, 30)

    home_rs_10 = recent_runs_for(home_history, 10)
    away_rs_10 = recent_runs_for(away_history, 10)
    home_ra_10 = recent_runs_against(home_history, 10)
    away_ra_10 = recent_runs_against(away_history, 10)
    home_rd_10 = diff(home_rs_10, home_ra_10)
    away_rd_10 = diff(away_rs_10, away_ra_10)

    home_rs_30 = recent_runs_for(home_history, 30)
    away_rs_30 = recent_runs_for(away_history, 30)
    home_ra_30 = recent_runs_against(home_history, 30)
    away_ra_30 = recent_runs_against(away_history, 30)
    home_rd_30 = diff(home_rs_30, home_ra_30)
    away_rd_30 = diff(away_rs_30, away_ra_30)

    return {
        "game_id": row.get("game_id") or "",
        "game_date": row.get("game_date") or "",
        "season": row.get("season") or "",
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "winner": row.get("winner") or "",
        "target_home_win": 1 if home_score > away_score else 0,
        "home_games_played_before": home_history.games_played,
        "away_games_played_before": away_history.games_played,
        "home_wins_before": home_history.wins,
        "away_wins_before": away_history.wins,
        "home_losses_before": home_history.losses,
        "away_losses_before": away_history.losses,
        "home_win_pct_before": round_float(home_win_pct),
        "away_win_pct_before": round_float(away_win_pct),
        "home_last_10_win_pct": round_float(home_last_10),
        "away_last_10_win_pct": round_float(away_last_10),
        "home_last_30_win_pct": round_float(home_last_30),
        "away_last_30_win_pct": round_float(away_last_30),
        "home_runs_scored_last_10": csv_value(home_rs_10),
        "away_runs_scored_last_10": csv_value(away_rs_10),
        "home_runs_allowed_last_10": csv_value(home_ra_10),
        "away_runs_allowed_last_10": csv_value(away_ra_10),
        "home_run_diff_last_10": csv_value(home_rd_10),
        "away_run_diff_last_10": csv_value(away_rd_10),
        "home_runs_scored_last_30": csv_value(home_rs_30),
        "away_runs_scored_last_30": csv_value(away_rs_30),
        "home_runs_allowed_last_30": csv_value(home_ra_30),
        "away_runs_allowed_last_30": csv_value(away_ra_30),
        "home_run_diff_last_30": csv_value(home_rd_30),
        "away_run_diff_last_30": csv_value(away_rd_30),
        "home_rest_days": csv_value(home_rest),
        "away_rest_days": csv_value(away_rest),
        "home_back_to_back": back_to_back(home_rest),
        "away_back_to_back": back_to_back(away_rest),
        "win_pct_diff": round_float(diff(home_win_pct, away_win_pct)),
        "last_10_win_pct_diff": round_float(diff(home_last_10, away_last_10)),
        "last_30_win_pct_diff": round_float(diff(home_last_30, away_last_30)),
        "run_diff_last_10_diff": csv_value(diff(home_rd_10, away_rd_10)),
        "run_diff_last_30_diff": csv_value(diff(home_rd_30, away_rd_30)),
        "rest_days_diff": csv_value(diff(home_rest, away_rest)),
    }


def write_features(rows: list[dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(report: dict[str, Any], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    args = parse_args()
    start_year = args.start_year
    end_year = args.end_year
    feature_output, report_output, expansion_report_output = output_paths(start_year, end_year)
    print("ASTRODDS MLB Engine - build_features")
    print("Building real moneyline features only. No model, predictions, ROI, CLV, calibration, or confidence will be created.")

    files = input_files(start_year, end_year)
    warnings: list[str] = []
    if not files:
        warnings.append(f"No processed MLB game CSV files found for the requested window {start_year}-{end_year}. Run fetch_data.py for the missing years first.")
        report = {
            "input_files_found": [],
            "seasons_included": [],
            "historical_window": f"{start_year}-{end_year}",
            "start_year": start_year,
            "end_year": end_year,
            "total_games_read": 0,
            "completed_games_used": 0,
            "incomplete_games_skipped": 0,
            "output_row_count": 0,
            "feature_columns": FEATURE_COLUMNS,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "output_csv": str(feature_output.relative_to(ENGINE_ROOT)),
        }
        write_report(report, report_output)
        if expansion_report_output is not None:
            write_report({**report, "expansion_report": True, "report_type": "historical_expansion"}, expansion_report_output)
        print(warnings[0])
        print(f"Report written: {report_output}")
        return

    games, total_read, malformed = read_games(files)
    histories: dict[tuple[int, str], TeamSeasonHistory] = {}
    feature_rows: list[dict[str, Any]] = []
    incomplete_skipped = 0
    no_prior_home = 0
    no_prior_away = 0
    home_less_than_10 = 0
    away_less_than_10 = 0
    home_missing_rest = 0
    away_missing_rest = 0
    seasons: set[int] = set()

    for row in games:
        season = row["_season_int"]
        seasons.add(season)
        home_team = str(row.get("home_team") or "")
        away_team = str(row.get("away_team") or "")
        home_history = get_history(histories, season, home_team)
        away_history = get_history(histories, season, away_team)

        if not is_completed(row):
            incomplete_skipped += 1
            continue

        if home_history.games_played == 0:
            no_prior_home += 1
        if away_history.games_played == 0:
            no_prior_away += 1
        if home_history.games_played < 10:
            home_less_than_10 += 1
        if away_history.games_played < 10:
            away_less_than_10 += 1
        if home_history.last_game_date is None:
            home_missing_rest += 1
        if away_history.last_game_date is None:
            away_missing_rest += 1

        feature_rows.append(build_feature_row(row, home_history, away_history))

        game_date = row["_parsed_game_date"]
        home_score = row["_home_score_int"]
        away_score = row["_away_score_int"]
        home_history.record_game(game_date, home_score, away_score)
        away_history.record_game(game_date, away_score, home_score)

    if malformed:
        warnings.append(f"Skipped {malformed} malformed rows with missing/invalid season or game_date.")
    if no_prior_home or no_prior_away:
        warnings.append(
            "Early-season rows with no prior team games use 0.5 win-percentage defaults; run/rest fields stay empty when unavailable."
        )
    if home_less_than_10 or away_less_than_10:
        warnings.append("Some rows have fewer than 10 prior games for one or both teams; last-10 features use available prior games only.")
    if incomplete_skipped:
        warnings.append("Scheduled/incomplete games were skipped as labeled training rows because winner/result is missing.")
    if 2026 in seasons:
        warnings.append("2026 rows are season-to-date only; only completed 2026 games with known winners are included.")

    write_features(feature_rows, feature_output)
    report = {
        "input_files_found": [str(path.relative_to(ENGINE_ROOT)) for path in files],
        "seasons_included": sorted(seasons),
        "historical_window": f"{start_year}-{end_year}",
        "start_year": start_year,
        "end_year": end_year,
        "total_games_read": total_read,
        "completed_games_used": len(feature_rows),
        "incomplete_games_skipped": incomplete_skipped,
        "malformed_games_skipped": malformed,
        "output_row_count": len(feature_rows),
        "feature_columns": FEATURE_COLUMNS,
        "output_csv": str(feature_output.relative_to(ENGINE_ROOT)),
        "report_json": str(report_output.relative_to(ENGINE_ROOT)),
        "limited_history_counts": {
            "home_no_prior_games": no_prior_home,
            "away_no_prior_games": no_prior_away,
            "home_less_than_10_prior_games": home_less_than_10,
            "away_less_than_10_prior_games": away_less_than_10,
            "home_missing_rest_days": home_missing_rest,
            "away_missing_rest_days": away_missing_rest,
        },
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_report(report, report_output)
    if expansion_report_output is not None:
        expansion_report = {
            **report,
            "report_type": "historical_expansion",
            "expansion_report": True,
            "expansion_report_json": str(expansion_report_output.relative_to(ENGINE_ROOT)),
        }
        write_report(expansion_report, expansion_report_output)

    print("Feature build completed.")
    print(f"- historical window: {start_year}-{end_year}")
    print(f"- input files: {len(files)}")
    print(f"- total games read: {total_read}")
    print(f"- completed games used: {len(feature_rows)}")
    print(f"- incomplete games skipped: {incomplete_skipped}")
    print(f"- output CSV: {feature_output}")
    print(f"- report JSON: {report_output}")
    if expansion_report_output is not None:
        print(f"- expansion report JSON: {expansion_report_output}")
    for warning in warnings:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
