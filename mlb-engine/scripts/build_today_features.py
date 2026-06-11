"""Build safe today MLB moneyline feature rows for research-only predictions.

This uses existing processed MLB schedule/results CSV files and replays completed
team history before each scheduled game. It does not use current-game results,
create picks, create market prices, calculate edge, or change ASTRODDS official
pick behavior.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_features import (
    FEATURE_COLUMNS,
    TeamSeasonHistory,
    back_to_back,
    csv_value,
    diff,
    get_history,
    is_completed,
    parse_date,
    parse_int,
    read_games,
    recent_runs_against,
    recent_runs_for,
    recent_win_pct,
    rest_days,
    round_float,
    win_pct,
)

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
TODAY_FEATURES_OUTPUT = PROCESSED_DIR / "mlb_today_features.csv"
TODAY_FEATURES_REPORT = PROCESSED_DIR / "mlb_today_features_report.json"
INPUT_PATTERN = "mlb_games_*.csv"
LATEST_SEASON = 2026

EXTRA_COLUMNS = [
    "data_quality",
    "data_quality_score",
    "missing_data_warnings",
    "feature_policy",
]

TODAY_FEATURE_COLUMNS = FEATURE_COLUMNS + EXTRA_COLUMNS

COMPLETED_STATUSES = {"final", "completed early", "game over"}
UNSAFE_TARGET_STATUSES = {"postponed", "cancelled", "canceled", "suspended"}


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def input_files() -> list[Path]:
    return sorted(
        path
        for path in PROCESSED_DIR.glob(INPUT_PATTERN)
        if path.name.startswith("mlb_games_") and path.name != TODAY_FEATURES_OUTPUT.name
    )


def status_text(row: dict[str, Any]) -> str:
    return str(row.get("status") or "").strip().lower()


def is_future_or_scheduled(row: dict[str, Any]) -> bool:
    status = status_text(row)
    if status in UNSAFE_TARGET_STATUSES:
        return False
    if status in COMPLETED_STATUSES:
        return False
    if row.get("winner"):
        return False
    return True


def current_utc_date() -> datetime.date:
    return datetime.now(timezone.utc).date()


def select_target_games(games: list[dict[str, Any]], warnings: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    today = current_utc_date()
    candidates: list[dict[str, Any]] = []
    skipped_postponed = 0

    for row in games:
        if row.get("_season_int") != LATEST_SEASON:
            continue
        if str(row.get("game_type") or "") != "R":
            continue
        game_date = row.get("_parsed_game_date")
        if not isinstance(game_date, datetime):
            continue
        if game_date.date() < today:
            continue
        if is_future_or_scheduled(row):
            candidates.append(row)
        elif status_text(row) in UNSAFE_TARGET_STATUSES:
            skipped_postponed += 1

    if skipped_postponed:
        warnings.append(f"Skipped {skipped_postponed} postponed/cancelled/suspended scheduled rows for today feature generation.")
    if not candidates:
        return [], None

    target_date = min(row["_parsed_game_date"].date() for row in candidates)
    target_rows = [row for row in candidates if row["_parsed_game_date"].date() == target_date]
    target_rows.sort(key=lambda row: (row["_parsed_game_date"], str(row.get("game_id") or "")))
    return target_rows, target_date.isoformat()


def build_histories_before_game(games: list[dict[str, Any]], target_row: dict[str, Any]) -> dict[tuple[int, str], TeamSeasonHistory]:
    histories: dict[tuple[int, str], TeamSeasonHistory] = {}
    target_date = target_row["_parsed_game_date"]
    target_season = target_row["_season_int"]

    for row in games:
        if row.get("_season_int") != target_season:
            continue
        game_date = row.get("_parsed_game_date")
        if not isinstance(game_date, datetime) or game_date >= target_date:
            continue
        if not is_completed(row):
            continue

        home_team = str(row.get("home_team") or "")
        away_team = str(row.get("away_team") or "")
        home_score = row.get("_home_score_int")
        away_score = row.get("_away_score_int")
        if not home_team or not away_team or home_score is None or away_score is None:
            continue

        home_history = get_history(histories, target_season, home_team)
        away_history = get_history(histories, target_season, away_team)
        home_history.record_game(game_date, int(home_score), int(away_score))
        away_history.record_game(game_date, int(away_score), int(home_score))

    return histories


def data_quality(home_history: TeamSeasonHistory, away_history: TeamSeasonHistory) -> tuple[str, int, list[str]]:
    warnings: list[str] = []
    min_games = min(home_history.games_played, away_history.games_played)

    if min_games >= 30:
        grade = "B"
        score = 72
    elif min_games >= 10:
        grade = "C"
        score = 60
        warnings.append("One or both teams have fewer than 30 completed prior games in the current season.")
    elif min_games > 0:
        grade = "D"
        score = 45
        warnings.append("One or both teams have fewer than 10 completed prior games in the current season.")
    else:
        grade = "F"
        score = 30
        warnings.append("No completed prior games found for at least one team in the current season.")

    warnings.extend([
        "Lineup data unavailable for today feature export.",
        "Pitcher data unavailable for today feature export.",
        "Bullpen data unavailable for today feature export.",
        "Weather impact not connected in Python today feature export.",
    ])
    return grade, score, warnings


def build_today_row(row: dict[str, Any], home_history: TeamSeasonHistory, away_history: TeamSeasonHistory) -> dict[str, Any]:
    home_team = str(row.get("home_team") or "")
    away_team = str(row.get("away_team") or "")
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

    grade, score, missing = data_quality(home_history, away_history)

    return {
        "game_id": row.get("game_id") or "",
        "game_date": row.get("game_date") or "",
        "season": row.get("season") or "",
        "home_team": home_team,
        "away_team": away_team,
        "home_score": "",
        "away_score": "",
        "winner": "",
        "target_home_win": "",
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
        "data_quality": grade,
        "data_quality_score": score,
        "missing_data_warnings": " | ".join(missing),
        "feature_policy": "research_only_no_current_game_results",
    }


def write_csv(rows: list[dict[str, Any]]) -> None:
    with TODAY_FEATURES_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TODAY_FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(report: dict[str, Any]) -> None:
    with TODAY_FEATURES_REPORT.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_today_features")
    print("Building research-only today moneyline features. No odds, edge, confidence, ROI, Telegram, or official picks will be created.")

    warnings: list[str] = []
    skipped: list[dict[str, str]] = []
    files = input_files()
    if not files:
        warnings.append("No processed MLB game CSV files found. Run fetch_data.py first.")
        write_report({
            "status": "missing_source_data",
            "input_files_found": [],
            "target_date": None,
            "rows_written": 0,
            "skipped_games": skipped,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(warnings[0])
        return

    games, total_read, malformed = read_games(files)
    target_games, target_date = select_target_games(games, warnings)
    rows: list[dict[str, Any]] = []

    for target in target_games:
        home_team = str(target.get("home_team") or "")
        away_team = str(target.get("away_team") or "")
        if not home_team or not away_team or not isinstance(target.get("_parsed_game_date"), datetime):
            skipped.append({"game_id": str(target.get("game_id") or ""), "reason": "missing team or game date"})
            continue
        histories = build_histories_before_game(games, target)
        season = int(target["_season_int"])
        home_history = get_history(histories, season, home_team)
        away_history = get_history(histories, season, away_team)
        rows.append(build_today_row(target, home_history, away_history))

    if malformed:
        warnings.append(f"Skipped {malformed} malformed source rows while reading processed schedules.")
    if target_date is None:
        warnings.append("No today or future scheduled MLB regular-season games were found in the latest 2026 schedule file.")
    if rows:
        warnings.append("Today features are research-only and do not include lineups, injuries, pitcher stats, market prices, or current-game results.")

    write_csv(rows)
    report = {
        "status": "ok" if rows else "no_today_features",
        "input_files_found": [str(path.relative_to(ENGINE_ROOT)) for path in files],
        "total_games_read": total_read,
        "target_date": target_date,
        "rows_written": len(rows),
        "feature_columns": TODAY_FEATURE_COLUMNS,
        "skipped_games": skipped,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_report(report)

    print("Today feature build completed.")
    print(f"- target date: {target_date or 'none'}")
    print(f"- rows written: {len(rows)}")
    print(f"- output CSV: {TODAY_FEATURES_OUTPUT}")
    print(f"- report JSON: {TODAY_FEATURES_REPORT}")
    for warning in warnings:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()