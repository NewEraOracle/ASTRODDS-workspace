"""Build safe bullpen-fatigue feature rows for ASTRODDS MLB Engine.

This is a research-only feature layer. It approximates bullpen workload from
public MLB schedule snapshots and recent game context. It does not create
predictions, picks, odds, ROI, CLV, calibration, or official betting outputs.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
BULLPEN_FEATURE_OUTPUT = PROCESSED_DIR / "mlb_bullpen_features.csv"
BULLPEN_FEATURE_REPORT = PROCESSED_DIR / "mlb_bullpen_features_report.json"
BULLPEN_MERGED_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_bullpen.csv"
BULLPEN_PITCHER_MERGED_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen.csv"
BASE_MONEYLINE_FEATURES = PROCESSED_DIR / "mlb_moneyline_features.csv"
PITCHER_MONEYLINE_FEATURES = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers.csv"
INPUT_PATTERN = "mlb_schedule_*.json"

BULLPEN_FEATURE_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_bullpen_usage_last_1",
    "away_bullpen_usage_last_1",
    "home_bullpen_usage_last_3",
    "away_bullpen_usage_last_3",
    "home_bullpen_usage_last_5",
    "away_bullpen_usage_last_5",
    "home_bullpen_runs_allowed_last_3",
    "away_bullpen_runs_allowed_last_3",
    "home_bullpen_runs_allowed_last_5",
    "away_bullpen_runs_allowed_last_5",
    "home_bullpen_avg_runs_allowed_last_3",
    "away_bullpen_avg_runs_allowed_last_3",
    "home_bullpen_fatigue_score",
    "away_bullpen_fatigue_score",
    "home_bullpen_risk",
    "away_bullpen_risk",
    "bullpen_data_quality",
    "bullpen_warnings",
]

APPROXIMATION_METHOD = "linescore innings after a starter cutoff plus recent-game stress proxy"


@dataclass
class BullpenGameRecord:
    date: datetime
    usage_units: float
    runs_allowed_proxy: int
    innings_proxy: int | None


@dataclass
class BullpenSeasonHistory:
    games: int = 0
    recent_games: deque[BullpenGameRecord] = field(default_factory=deque)
    last_game_date: datetime | None = None

    def record_game(self, game_date: datetime, usage_units: float, runs_allowed_proxy: int, innings_proxy: int | None) -> None:
        self.games += 1
        self.recent_games.append(
            BullpenGameRecord(
                date=game_date,
                usage_units=usage_units,
                runs_allowed_proxy=runs_allowed_proxy,
                innings_proxy=innings_proxy,
            )
        )
        while len(self.recent_games) > 30:
            self.recent_games.popleft()
        self.last_game_date = game_date


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def is_record(value: Any) -> bool:
    return isinstance(value, dict)


def optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def optional_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number else None
    if isinstance(value, str) and value.strip():
        try:
            number = float(value)
            return number if number == number else None
        except ValueError:
            return None
    return None


def parse_date(value: Any) -> datetime | None:
    text = optional_string(value)
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
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


def round_float(value: float | None, digits: int = 4) -> float | str:
    if value is None:
        return ""
    return round(value, digits)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def unique_strings(values: list[str | None]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def input_files() -> list[Path]:
    return sorted(
        path
        for path in RAW_DIR.glob(INPUT_PATTERN)
        if path.name.startswith("mlb_schedule_")
    )


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
        payload = json.loads(raw)
        return payload if is_record(payload) else None
    except Exception:
        return None


def all_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        if not is_record(date_block):
            continue
        for game in date_block.get("games", []):
            if is_record(game):
                games.append(game)
    return games


def normalize_game(game: dict[str, Any], season_fallback: int | None) -> dict[str, Any] | None:
    game_date = parse_date(game.get("gameDate") or game.get("officialDate"))
    season = optional_number(game.get("season")) or season_fallback
    game_pk = optional_number(game.get("gamePk"))
    if game_date is None or season is None or game_pk is None:
        return None

    return {
        **game,
        "_parsed_game_date": game_date,
        "_season_int": season,
        "_game_pk_int": game_pk,
    }


def read_games(files: list[Path]) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    games: list[dict[str, Any]] = []
    total_read = 0
    malformed = 0
    warnings: list[str] = []

    for file_path in files:
        payload = load_json_file(file_path)
        if payload is None:
            warnings.append(f"Skipped unreadable raw schedule snapshot: {file_path.name}.")
            continue
        year = optional_number(file_path.stem.split("_")[-1])
        for game in all_games(payload):
            total_read += 1
            normalized = normalize_game(game, year)
            if normalized is None:
                malformed += 1
                continue
            games.append(normalized)

    games.sort(key=lambda row: (row["_parsed_game_date"], row["_game_pk_int"]))
    return games, total_read, malformed, warnings


def is_completed(row: dict[str, Any]) -> bool:
    status = row.get("status")
    if not is_record(status):
        return False
    detailed = optional_string(status.get("detailedState")) or ""
    abstract = optional_string(status.get("abstractGameState")) or ""
    teams = row.get("teams")
    if not is_record(teams):
        return False
    home = teams.get("home")
    away = teams.get("away")
    if not is_record(home) or not is_record(away):
        return False
    home_score = optional_number(home.get("score"))
    away_score = optional_number(away.get("score"))
    return bool(home_score is not None and away_score is not None and (abstract.lower() == "final" or "final" in detailed.lower()))


def team_name(game: dict[str, Any], side: str) -> str:
    teams = game.get("teams")
    if not is_record(teams):
        return ""
    side_block = teams.get(side)
    if not is_record(side_block):
        return ""
    team = side_block.get("team")
    if not is_record(team):
        return ""
    return optional_string(team.get("name")) or ""


def team_score(game: dict[str, Any], side: str) -> int | None:
    teams = game.get("teams")
    if not is_record(teams):
        return None
    side_block = teams.get(side)
    if not is_record(side_block):
        return None
    return optional_number(side_block.get("score"))


def game_linescore(game: dict[str, Any]) -> list[dict[str, Any]]:
    linescore = game.get("linescore")
    if not is_record(linescore):
        return []
    innings = linescore.get("innings")
    if not isinstance(innings, list):
        return []
    return [inning for inning in innings if is_record(inning)]


def bullpen_cutoff(scheduled_innings: int) -> int:
    return 4 if scheduled_innings <= 7 else 5


def summarize_current_game_bullpen(game: dict[str, Any], side: str) -> tuple[float | None, int | None, int | None, list[str], bool]:
    innings = game_linescore(game)
    scheduled_innings = optional_number(game.get("scheduledInnings")) or len(innings) or 9
    home_score = team_score(game, "home")
    away_score = team_score(game, "away")
    opponent_side = "away" if side == "home" else "home"
    opponent_final_score = team_score(game, opponent_side)
    side_final_score = team_score(game, side)
    warnings: list[str] = []

    if not innings or home_score is None or away_score is None:
        if opponent_final_score is None:
            return None, None, None, ["Bullpen proxy unavailable because linescore and final scores were missing."], False
        runs_allowed_proxy = opponent_final_score
        usage_units = runs_allowed_proxy * 0.25 + (1.0 if runs_allowed_proxy >= 5 else 0.25 if runs_allowed_proxy >= 3 else 0.0)
        warnings.append("Linescore innings unavailable; bullpen workload estimated from final score only.")
        warnings.append("Bullpen workload is an approximation based on public game results and recent stress proxies.")
        return round(usage_units, 4), runs_allowed_proxy, None, unique_strings(warnings), True

    cut = bullpen_cutoff(scheduled_innings)
    bullpen_innings = max(0, len(innings) - cut)
    extra_innings = max(0, len(innings) - scheduled_innings)
    if side == "home":
        opponent_runs = sum(optional_number(inning.get("away", {}).get("runs")) or 0 for inning in innings[cut:])
    else:
        opponent_runs = sum(optional_number(inning.get("home", {}).get("runs")) or 0 for inning in innings[cut:])
    margin = abs(home_score - away_score)
    close_game_bonus = 0.5 if margin <= 2 else 0.25 if margin <= 4 else 0.0
    high_scoring_bonus = 0.25 if opponent_runs >= 5 else 0.0
    usage_units = bullpen_innings + (opponent_runs * 0.25) + (extra_innings * 0.5) + close_game_bonus + high_scoring_bonus
    warnings.append(f"Bullpen workload is approximated from innings {cut + 1}+ after a starter cutoff.")
    warnings.append("Bullpen workload is an approximation; exact bullpen innings are not publicly exposed in the saved schedule snapshots.")
    if side_final_score is None or opponent_final_score is None:
        warnings.append("Final score context incomplete; bullpen proxy used conservative defaults.")
    return round(usage_units, 4), opponent_runs, bullpen_innings, unique_strings(warnings), True


def recent_slice(history: BullpenSeasonHistory, limit: int) -> list[BullpenGameRecord]:
    if limit <= 0:
        return []
    return list(history.recent_games)[-limit:]


def sum_recent_usage(history: BullpenSeasonHistory, limit: int) -> float | None:
    records = recent_slice(history, limit)
    if not records:
        return None
    return round(sum(record.usage_units for record in records), 4)


def sum_recent_runs_allowed(history: BullpenSeasonHistory, limit: int) -> int | None:
    records = recent_slice(history, limit)
    if not records:
        return None
    return sum(record.runs_allowed_proxy for record in records)


def avg_recent_runs_allowed(history: BullpenSeasonHistory, limit: int) -> float | None:
    records = recent_slice(history, limit)
    if not records:
        return None
    return sum(record.runs_allowed_proxy for record in records) / len(records)


def bullpen_fatigue_score(last_1: float | None, last_3: float | None, last_5: float | None, runs_last_3: int | None) -> float | None:
    if last_1 is None and last_3 is None and last_5 is None and runs_last_3 is None:
        return None
    score = 0.0
    if last_1 is not None:
        score += min(1.0, last_1 / 4.0) * 0.25
    if last_3 is not None:
        score += min(1.0, last_3 / 12.0) * 0.35
    if last_5 is not None:
        score += min(1.0, last_5 / 20.0) * 0.25
    if runs_last_3 is not None:
        score += min(1.0, runs_last_3 / 12.0) * 0.15
    return round(clamp(score), 4)


def bullpen_risk_score(fatigue: float | None, runs_last_5: int | None) -> float | None:
    if fatigue is None and runs_last_5 is None:
        return None
    score = (fatigue or 0.0) * 0.65
    if runs_last_5 is not None:
        score += min(1.0, runs_last_5 / 15.0) * 0.35
    return round(clamp(score), 4)


def recent_values(history: BullpenSeasonHistory, limit: int) -> list[BullpenGameRecord]:
    return recent_slice(history, limit)


def quality_for_row(home_history: BullpenSeasonHistory, away_history: BullpenSeasonHistory) -> str:
    home_count = len(home_history.recent_games)
    away_count = len(away_history.recent_games)
    if home_count == 0 or away_count == 0:
        return "missing"
    if home_count >= 5 and away_count >= 5:
        return "high"
    if home_count >= 3 and away_count >= 3:
        return "medium"
    return "low"


def build_row(
    row: dict[str, Any],
    home_history: BullpenSeasonHistory,
    away_history: BullpenSeasonHistory,
) -> dict[str, Any]:
    home_last_1 = recent_values(home_history, 1)
    away_last_1 = recent_values(away_history, 1)
    home_last_3 = recent_values(home_history, 3)
    away_last_3 = recent_values(away_history, 3)
    home_last_5 = recent_values(home_history, 5)
    away_last_5 = recent_values(away_history, 5)

    home_usage_last_1 = home_last_1[-1].usage_units if home_last_1 else None
    away_usage_last_1 = away_last_1[-1].usage_units if away_last_1 else None
    home_usage_last_3 = sum_recent_usage(home_history, 3)
    away_usage_last_3 = sum_recent_usage(away_history, 3)
    home_usage_last_5 = sum_recent_usage(home_history, 5)
    away_usage_last_5 = sum_recent_usage(away_history, 5)
    home_runs_allowed_last_3 = sum_recent_runs_allowed(home_history, 3)
    away_runs_allowed_last_3 = sum_recent_runs_allowed(away_history, 3)
    home_runs_allowed_last_5 = sum_recent_runs_allowed(home_history, 5)
    away_runs_allowed_last_5 = sum_recent_runs_allowed(away_history, 5)
    home_avg_runs_allowed_last_3 = avg_recent_runs_allowed(home_history, 3)
    away_avg_runs_allowed_last_3 = avg_recent_runs_allowed(away_history, 3)
    home_fatigue = bullpen_fatigue_score(home_usage_last_1, home_usage_last_3, home_usage_last_5, home_runs_allowed_last_3)
    away_fatigue = bullpen_fatigue_score(away_usage_last_1, away_usage_last_3, away_usage_last_5, away_runs_allowed_last_3)
    home_risk = bullpen_risk_score(home_fatigue, home_runs_allowed_last_5)
    away_risk = bullpen_risk_score(away_fatigue, away_runs_allowed_last_5)
    quality = quality_for_row(home_history, away_history)

    warnings: list[str] = []
    if quality == "missing":
        warnings.append("Bullpen history unavailable before this game.")
    if quality == "low":
        warnings.append("Limited prior bullpen history; early rows are conservative.")
    warnings.append("Bullpen workload is an approximation from public schedule data and recent game stress.")

    return {
        "game_id": row.get("game_id") or "",
        "game_date": row.get("game_date") or "",
        "season": row.get("season") or "",
        "home_team": row.get("home_team") or "",
        "away_team": row.get("away_team") or "",
        "home_bullpen_usage_last_1": csv_value(round_float(home_usage_last_1)),
        "away_bullpen_usage_last_1": csv_value(round_float(away_usage_last_1)),
        "home_bullpen_usage_last_3": csv_value(round_float(home_usage_last_3)),
        "away_bullpen_usage_last_3": csv_value(round_float(away_usage_last_3)),
        "home_bullpen_usage_last_5": csv_value(round_float(home_usage_last_5)),
        "away_bullpen_usage_last_5": csv_value(round_float(away_usage_last_5)),
        "home_bullpen_runs_allowed_last_3": csv_value(home_runs_allowed_last_3),
        "away_bullpen_runs_allowed_last_3": csv_value(away_runs_allowed_last_3),
        "home_bullpen_runs_allowed_last_5": csv_value(home_runs_allowed_last_5),
        "away_bullpen_runs_allowed_last_5": csv_value(away_runs_allowed_last_5),
        "home_bullpen_avg_runs_allowed_last_3": csv_value(round_float(home_avg_runs_allowed_last_3)),
        "away_bullpen_avg_runs_allowed_last_3": csv_value(round_float(away_avg_runs_allowed_last_3)),
        "home_bullpen_fatigue_score": csv_value(round_float(home_fatigue)),
        "away_bullpen_fatigue_score": csv_value(round_float(away_fatigue)),
        "home_bullpen_risk": csv_value(round_float(home_risk)),
        "away_bullpen_risk": csv_value(round_float(away_risk)),
        "bullpen_data_quality": quality,
        "bullpen_warnings": " | ".join(unique_strings(warnings)),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def merge_with_moneyline_features(source_csv: Path, output_csv: Path, bullpen_rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    if not source_csv.exists():
        warnings.append(f"Baseline merge skipped because {source_csv.name} is missing.")
        return {
            "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
            "enhanced_rows_written": 0,
            "enhanced_missing_bullpen_rows": 0,
            "enhanced_output_csv": None,
            "enhanced_columns": [],
        }

    with source_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        base_rows = list(reader)
        base_columns = reader.fieldnames or []

    bullpen_index = {
        (str(row.get("game_id") or ""), str(row.get("season") or "")): row
        for row in bullpen_rows
    }

    merged_columns = list(base_columns)
    for column in BULLPEN_FEATURE_COLUMNS:
        if column not in merged_columns:
            merged_columns.append(column)

    merged_rows: list[dict[str, Any]] = []
    missing_bullpen_rows = 0
    for base_row in base_rows:
        key = (str(base_row.get("game_id") or ""), str(base_row.get("season") or ""))
        bullpen_row = bullpen_index.get(key)
        merged_row = dict(base_row)
        for column in BULLPEN_FEATURE_COLUMNS:
            merged_row[column] = bullpen_row.get(column, "") if bullpen_row else ""
        if bullpen_row is None:
            missing_bullpen_rows += 1
        merged_rows.append(merged_row)

    write_csv(output_csv, merged_rows, merged_columns)
    return {
        "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
        "enhanced_rows_written": len(merged_rows),
        "enhanced_missing_bullpen_rows": missing_bullpen_rows,
        "enhanced_output_csv": str(output_csv.relative_to(ENGINE_ROOT)),
        "enhanced_columns": merged_columns,
    }


def overall_quality(summary: dict[str, int]) -> str:
    total = sum(summary.values())
    if total <= 0:
        return "missing"
    if summary["high"] and not summary["medium"] and not summary["low"] and not summary["missing"]:
        return "high"
    if summary["high"] + summary["medium"] > summary["low"] + summary["missing"]:
        return "medium"
    if summary["high"] + summary["medium"] + summary["low"] > 0:
        return "low"
    return "missing"


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_bullpen_features")
    print("Building research-only bullpen fatigue features. No picks, odds, ROI, CLV, calibration, Telegram, or official betting actions will be created.")

    warnings: list[str] = []
    files = input_files()
    if not files:
        warnings.append("No raw MLB schedule JSON files found. Run fetch_data.py first.")
        write_json(
            BULLPEN_FEATURE_REPORT,
            {
                "status": "missing_source_data",
                "input_files_found": [],
                "total_games_read": 0,
                "completed_games_used": 0,
                "games_with_bullpen_data": 0,
                "games_missing_bullpen_data": 0,
                "games_approximated_bullpen_data": 0,
                "approximation_method": APPROXIMATION_METHOD,
                "approximation_used": False,
                "output_row_count": 0,
                "feature_columns": BULLPEN_FEATURE_COLUMNS,
                "bullpen_data_quality_summary": {"high": 0, "medium": 0, "low": 0, "missing": 0},
                "merged_enhanced_output": None,
                "warnings": warnings,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(warnings[0])
        return

    games, total_read, malformed, file_warnings = read_games(files)
    warnings.extend(file_warnings)
    seasons = sorted({row["_season_int"] for row in games})
    histories: dict[tuple[int, str], BullpenSeasonHistory] = {}
    bullpen_rows: list[dict[str, Any]] = []
    quality_counts: Counter[str] = Counter()
    missing_bullpen_rows = 0

    for row in games:
        if not is_completed(row):
            continue

        season = row["_season_int"]
        home_team = team_name(row, "home")
        away_team = team_name(row, "away")
        home_history_key = (season, home_team.strip().lower())
        away_history_key = (season, away_team.strip().lower())
        if home_history_key not in histories:
            histories[home_history_key] = BullpenSeasonHistory()
        if away_history_key not in histories:
            histories[away_history_key] = BullpenSeasonHistory()
        home_history = histories[home_history_key]
        away_history = histories[away_history_key]

        bullpen_rows.append(build_row(row, home_history, away_history))
        quality = bullpen_rows[-1]["bullpen_data_quality"]
        quality_counts[quality] += 1
        if quality == "missing":
            missing_bullpen_rows += 1

        home_load, home_runs_allowed, home_innings_proxy, home_load_warnings, _ = summarize_current_game_bullpen(row, "home")
        away_load, away_runs_allowed, away_innings_proxy, away_load_warnings, _ = summarize_current_game_bullpen(row, "away")
        warnings.extend(home_load_warnings[:1] if home_load_warnings else [])
        warnings.extend(away_load_warnings[:1] if away_load_warnings else [])

        game_date = row["_parsed_game_date"]
        if home_load is not None and home_runs_allowed is not None:
            home_history.record_game(game_date, home_load, home_runs_allowed, home_innings_proxy)
        if away_load is not None and away_runs_allowed is not None:
            away_history.record_game(game_date, away_load, away_runs_allowed, away_innings_proxy)

    if malformed:
        warnings.append(f"Skipped {malformed} malformed rows with missing/invalid season or game_date.")
    if missing_bullpen_rows:
        warnings.append("Early bullpen rows can be blank until prior team game history exists.")
    if bullpen_rows:
        warnings.append("Bullpen workload is an approximation based on public linescore snapshots and recent-game stress, not exact bullpen innings.")
    if 2026 in seasons:
        warnings.append("2026 is season-to-date only; bullpen features remain research-only and should not be treated as finalized model inputs yet.")

    write_csv(BULLPEN_FEATURE_OUTPUT, bullpen_rows, BULLPEN_FEATURE_COLUMNS)

    merged_summary = merge_with_moneyline_features(BASE_MONEYLINE_FEATURES, BULLPEN_MERGED_OUTPUT, bullpen_rows, warnings)
    pitcher_merged_summary = merge_with_moneyline_features(PITCHER_MONEYLINE_FEATURES, BULLPEN_PITCHER_MERGED_OUTPUT, bullpen_rows, warnings)

    bullpen_data_quality_summary = {
        "high": quality_counts.get("high", 0),
        "medium": quality_counts.get("medium", 0),
        "low": quality_counts.get("low", 0),
        "missing": quality_counts.get("missing", 0),
    }
    data_quality = overall_quality(bullpen_data_quality_summary)
    games_with_bullpen_data = len(bullpen_rows) - missing_bullpen_rows
    approximation_used = bool(bullpen_rows)

    report = {
        "status": "available" if games_with_bullpen_data else "missing",
        "input_files_found": [str(path.relative_to(ENGINE_ROOT)) for path in files],
        "seasons_included": seasons,
        "total_games_read": total_read,
        "completed_games_used": len(bullpen_rows),
        "games_with_bullpen_data": games_with_bullpen_data,
        "games_missing_bullpen_data": missing_bullpen_rows,
        "games_approximated_bullpen_data": len(bullpen_rows),
        "approximation_method": APPROXIMATION_METHOD,
        "approximation_used": approximation_used,
        "output_row_count": len(bullpen_rows),
        "feature_columns": BULLPEN_FEATURE_COLUMNS,
        "bullpen_data_quality": data_quality,
        "bullpen_data_quality_summary": bullpen_data_quality_summary,
        "merged_enhanced_output": merged_summary,
        "merged_pitcher_enhanced_output": pitcher_merged_summary,
        "warnings": unique_strings([
            *warnings,
            "Bullpen feature layer is research only and does not change official picks, Strong Buys, Telegram alerts, or real-money behavior.",
        ]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(BULLPEN_FEATURE_REPORT, report)

    print("Bullpen feature build completed.")
    print(f"- input files: {len(files)}")
    print(f"- total games read: {total_read}")
    print(f"- completed games used: {len(bullpen_rows)}")
    print(f"- games with bullpen data: {games_with_bullpen_data}")
    print(f"- games missing bullpen data: {missing_bullpen_rows}")
    print(f"- output CSV: {BULLPEN_FEATURE_OUTPUT}")
    print(f"- report JSON: {BULLPEN_FEATURE_REPORT}")
    if merged_summary.get("enhanced_output_csv"):
        print(f"- merged moneyline CSV: {merged_summary['enhanced_output_csv']}")
    if pitcher_merged_summary.get("enhanced_output_csv"):
        print(f"- merged pitcher+bullpen CSV: {pitcher_merged_summary['enhanced_output_csv']}")
    for warning in report["warnings"]:
        print(f"Warning: {warning}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
