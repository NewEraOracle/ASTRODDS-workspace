"""Build safe starting pitcher feature rows for ASTRODDS MLB Engine.

This is a research-only feature layer. It does not create predictions, picks,
odds, ROI, CLV, calibration, or official betting outputs.
"""
from __future__ import annotations

import csv
import json
import socket
from collections import Counter, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from build_features import csv_value, is_completed, parse_date, parse_int, read_games, round_float
from fetch_data import fetch_json

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
PITCHER_FEATURE_OUTPUT = PROCESSED_DIR / "mlb_pitcher_features.csv"
PITCHER_FEATURE_REPORT = PROCESSED_DIR / "mlb_pitcher_features_report.json"
ENHANCED_MONEYLINE_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers.csv"
BASE_MONEYLINE_FEATURES = PROCESSED_DIR / "mlb_moneyline_features.csv"
INPUT_PATTERN = "mlb_games_*.csv"
SUPPORTED_YEARS = (2023, 2024, 2025, 2026)
PITCHER_FEATURE_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_starting_pitcher_id",
    "away_starting_pitcher_id",
    "home_starting_pitcher_name",
    "away_starting_pitcher_name",
    "home_pitcher_games_started_before",
    "away_pitcher_games_started_before",
    "home_pitcher_rest_days",
    "away_pitcher_rest_days",
    "home_pitcher_runs_allowed_last_3",
    "away_pitcher_runs_allowed_last_3",
    "home_pitcher_runs_allowed_last_10",
    "away_pitcher_runs_allowed_last_10",
    "home_pitcher_avg_runs_allowed_last_3",
    "away_pitcher_avg_runs_allowed_last_3",
    "home_pitcher_avg_runs_allowed_last_10",
    "away_pitcher_avg_runs_allowed_last_10",
    "home_pitcher_team_win_rate_started_before",
    "away_pitcher_team_win_rate_started_before",
    "home_pitcher_status",
    "away_pitcher_status",
    "pitcher_data_quality",
    "pitcher_warnings",
]


@dataclass
class PitcherStartRecord:
    date: datetime
    runs_allowed: int
    team_won: bool


@dataclass
class PitcherSeasonHistory:
    starts: int = 0
    team_wins: int = 0
    team_losses: int = 0
    recent_starts: deque[PitcherStartRecord] = field(default_factory=deque)
    last_start_date: datetime | None = None

    def record_start(self, game_date: datetime, runs_allowed: int, team_won: bool) -> None:
        self.starts += 1
        if team_won:
            self.team_wins += 1
        else:
            self.team_losses += 1
        self.recent_starts.append(PitcherStartRecord(date=game_date, runs_allowed=runs_allowed, team_won=team_won))
        while len(self.recent_starts) > 30:
            self.recent_starts.popleft()
        self.last_start_date = game_date


@dataclass
class SourceDiagnostics:
    year: int
    source_label: str
    endpoint_label: str
    status: str
    http_status: int | None
    timeout: bool
    sanitized_url: str
    error_message: str | None
    retry_count: int
    source_mode: str


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
            return int(value)
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


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def season_date_range(year: int) -> tuple[str, str]:
    return f"{year}-01-01", f"{year}-12-31"


def build_pitcher_schedule_url(year: int) -> str:
    start_date, end_date = season_date_range(year)
    query = urlencode(
        {
            "sportId": 1,
            "season": year,
            "gameType": "R",
            "startDate": start_date,
            "endDate": end_date,
            "hydrate": "team,venue,linescore,probablePitcher",
        }
    )
    return f"https://statsapi.mlb.com/api/v1/schedule?{query}"


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


def pitcher_entry_from_value(value: Any, status: str) -> dict[str, Any] | None:
    if not is_record(value):
        return None
    person = value.get("person") if is_record(value.get("person")) else None
    pitcher_id = optional_string(value.get("id") or value.get("personId") or (person.get("id") if is_record(person) else None))
    pitcher_name = optional_string(
        value.get("fullName")
        or value.get("name")
        or (person.get("fullName") if is_record(person) else None)
    )
    if not pitcher_id and not pitcher_name:
        return None
    return {
        "pitcher_id": pitcher_id,
        "pitcher_name": pitcher_name,
        "status": status,
    }


def extract_pitcher_entry(game: dict[str, Any], side: str) -> dict[str, Any] | None:
    teams = game.get("teams", {})
    if not is_record(teams):
        return None
    side_block = teams.get(side, {})
    if not is_record(side_block):
        return None

    game_data = game.get("gameData", {})
    if is_record(game_data):
        probable_pitchers = game_data.get("probablePitchers", {})
        if is_record(probable_pitchers):
            entry = pitcher_entry_from_value(probable_pitchers.get(side), "projected")
            if entry:
                return entry

    for key in ("probablePitcher", "startingPitcher"):
        entry = pitcher_entry_from_value(side_block.get(key), "projected")
        if entry:
            return entry

    return None


def extract_pitcher_map(payload: dict[str, Any], season: int) -> dict[tuple[int, str], dict[str, dict[str, Any] | None]]:
    mapping: dict[tuple[int, str], dict[str, dict[str, Any] | None]] = {}
    for game in all_games(payload):
        game_id = optional_string(game.get("gamePk") or game.get("game_id"))
        if not game_id:
            continue
        key = (season, game_id)
        status_block = game.get("status")
        detailed_state = optional_string(status_block.get("detailedState")) if is_record(status_block) else ""
        mapping[key] = {
            "home": extract_pitcher_entry(game, "home"),
            "away": extract_pitcher_entry(game, "away"),
            "final": "final" in (detailed_state or "").lower(),
        }
    return mapping


def merge_pitcher_maps(
    base: dict[tuple[int, str], dict[str, dict[str, Any] | None]],
    override: dict[tuple[int, str], dict[str, dict[str, Any] | None]],
) -> dict[tuple[int, str], dict[str, dict[str, Any] | None]]:
    merged = dict(base)
    for key, pitch_data in override.items():
        if key not in merged:
            merged[key] = pitch_data
            continue
        current = merged[key]
        merged[key] = {
            "home": current.get("home") or pitch_data.get("home"),
            "away": current.get("away") or pitch_data.get("away"),
            "final": bool(current.get("final")) or bool(pitch_data.get("final")),
        }
    return merged


def recent_slices(history: PitcherSeasonHistory, limit: int) -> list[PitcherStartRecord]:
    if limit <= 0:
        return []
    return list(history.recent_starts)[-limit:]


def sum_recent_runs(history: PitcherSeasonHistory, limit: int) -> int | None:
    records = recent_slices(history, limit)
    if not records:
        return None
    return sum(record.runs_allowed for record in records)


def avg_recent_runs(history: PitcherSeasonHistory, limit: int) -> float | None:
    records = recent_slices(history, limit)
    if not records:
        return None
    return sum(record.runs_allowed for record in records) / len(records)


def rest_days(history: PitcherSeasonHistory, current_date: datetime) -> int | None:
    if history.last_start_date is None:
        return None
    return max(0, (current_date.date() - history.last_start_date.date()).days)


def win_rate_before(history: PitcherSeasonHistory) -> float | None:
    if history.starts <= 0:
        return None
    return history.team_wins / history.starts


def pitcher_quality(
    home_pitcher: dict[str, Any] | None,
    away_pitcher: dict[str, Any] | None,
    home_history: PitcherSeasonHistory | None,
    away_history: PitcherSeasonHistory | None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    home_present = home_pitcher is not None
    away_present = away_pitcher is not None

    if not home_present and not away_present:
        return "missing", ["Starting pitcher data unavailable."]

    if not home_present:
        warnings.append("Home starting pitcher unavailable.")
    if not away_present:
        warnings.append("Away starting pitcher unavailable.")

    home_starts = home_history.starts if home_history is not None else 0
    away_starts = away_history.starts if away_history is not None else 0
    min_starts = min(home_starts if home_present else 0, away_starts if away_present else 0)
    max_starts = max(home_starts if home_present else 0, away_starts if away_present else 0)

    if home_present and away_present and min_starts >= 10:
        quality = "high"
    elif home_present and away_present and min_starts >= 3:
        quality = "medium"
    elif max_starts >= 1:
        quality = "low"
    else:
        quality = "missing"

    if home_present and home_starts < 3:
        warnings.append("Home starting pitcher has limited prior start history.")
    if away_present and away_starts < 3:
        warnings.append("Away starting pitcher has limited prior start history.")
    if home_present and home_starts == 0:
        warnings.append("Home starting pitcher has no prior starts in the current season.")
    if away_present and away_starts == 0:
        warnings.append("Away starting pitcher has no prior starts in the current season.")

    return quality, warnings


def load_pitcher_payload(year: int, warnings: list[str], diagnostics: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw_path = RAW_DIR / f"mlb_schedule_{year}.json"
    local_payload = load_json_file(raw_path)
    local_map = extract_pitcher_map(local_payload, year) if local_payload else {}
    local_has_pitchers = any(entry.get("home") or entry.get("away") for entry in local_map.values())

    if local_payload and local_has_pitchers:
        diagnostics.append(
            {
                "year": year,
                "source_label": "MLB StatsAPI",
                "endpoint_label": "schedule raw",
                "status": "LOCAL",
                "http_status": None,
                "timeout": False,
                "sanitized_url": sanitize_url(str(raw_path)),
                "error_message": None,
                "retry_count": 0,
                "source_mode": "local_raw",
                "pitcher_entries": sum(1 for entry in local_map.values() if entry.get("home") or entry.get("away")),
            }
        )
        return local_payload

    if local_payload and not local_has_pitchers:
        warnings.append(f"Year {year}: local schedule snapshot has no probable starting pitcher fields; trying a safe year-level hydrate.")

    payload, fetch_diagnostics = fetch_json(build_pitcher_schedule_url(year), timeout_seconds=25.0, max_retries=1)
    diagnostics.append({**asdict(fetch_diagnostics), "year": year, "source_mode": "remote_hydrate"})
    if payload is None:
        if local_payload is None:
            warnings.append(f"Year {year}: pitcher hydrate fetch failed and no local raw schedule snapshot was available.")
        else:
            warnings.append(f"Year {year}: pitcher hydrate fetch failed; using local raw schedule snapshot with missing pitcher fields.")
        return local_payload

    return payload


def build_row(
    row: dict[str, Any],
    pitcher_entry: dict[str, dict[str, Any] | None] | None,
    home_history: PitcherSeasonHistory | None,
    away_history: PitcherSeasonHistory | None,
) -> dict[str, Any]:
    home_pitcher = pitcher_entry.get("home") if pitcher_entry else None
    away_pitcher = pitcher_entry.get("away") if pitcher_entry else None
    game_date = row["_parsed_game_date"]

    home_starts = home_history.starts if home_pitcher and home_history else None
    away_starts = away_history.starts if away_pitcher and away_history else None
    home_rest = rest_days(home_history, game_date) if home_pitcher and home_history else None
    away_rest = rest_days(away_history, game_date) if away_pitcher and away_history else None
    home_runs_3 = sum_recent_runs(home_history, 3) if home_pitcher and home_history else None
    away_runs_3 = sum_recent_runs(away_history, 3) if away_pitcher and away_history else None
    home_runs_10 = sum_recent_runs(home_history, 10) if home_pitcher and home_history else None
    away_runs_10 = sum_recent_runs(away_history, 10) if away_pitcher and away_history else None
    home_avg_3 = avg_recent_runs(home_history, 3) if home_pitcher and home_history else None
    away_avg_3 = avg_recent_runs(away_history, 3) if away_pitcher and away_history else None
    home_avg_10 = avg_recent_runs(home_history, 10) if home_pitcher and home_history else None
    away_avg_10 = avg_recent_runs(away_history, 10) if away_pitcher and away_history else None
    home_wr = win_rate_before(home_history) if home_pitcher and home_history else None
    away_wr = win_rate_before(away_history) if away_pitcher and away_history else None

    quality, warnings = pitcher_quality(home_pitcher, away_pitcher, home_history, away_history)

    return {
        "game_id": row.get("game_id") or "",
        "game_date": row.get("game_date") or "",
        "season": row.get("season") or "",
        "home_team": row.get("home_team") or "",
        "away_team": row.get("away_team") or "",
        "home_starting_pitcher_id": home_pitcher.get("pitcher_id") if home_pitcher else "",
        "away_starting_pitcher_id": away_pitcher.get("pitcher_id") if away_pitcher else "",
        "home_starting_pitcher_name": home_pitcher.get("pitcher_name") if home_pitcher else "",
        "away_starting_pitcher_name": away_pitcher.get("pitcher_name") if away_pitcher else "",
        "home_pitcher_games_started_before": csv_value(home_starts),
        "away_pitcher_games_started_before": csv_value(away_starts),
        "home_pitcher_rest_days": csv_value(home_rest),
        "away_pitcher_rest_days": csv_value(away_rest),
        "home_pitcher_runs_allowed_last_3": csv_value(home_runs_3),
        "away_pitcher_runs_allowed_last_3": csv_value(away_runs_3),
        "home_pitcher_runs_allowed_last_10": csv_value(home_runs_10),
        "away_pitcher_runs_allowed_last_10": csv_value(away_runs_10),
        "home_pitcher_avg_runs_allowed_last_3": round_float(home_avg_3),
        "away_pitcher_avg_runs_allowed_last_3": round_float(away_avg_3),
        "home_pitcher_avg_runs_allowed_last_10": round_float(home_avg_10),
        "away_pitcher_avg_runs_allowed_last_10": round_float(away_avg_10),
        "home_pitcher_team_win_rate_started_before": round_float(home_wr),
        "away_pitcher_team_win_rate_started_before": round_float(away_wr),
        "home_pitcher_status": "confirmed" if home_pitcher else "missing",
        "away_pitcher_status": "confirmed" if away_pitcher else "missing",
        "pitcher_data_quality": quality,
        "pitcher_warnings": " | ".join(dict.fromkeys(warnings)),
    }


def write_pitcher_csv(rows: list[dict[str, Any]]) -> None:
    with PITCHER_FEATURE_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PITCHER_FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def merge_with_moneyline_features(pitcher_rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    if not BASE_MONEYLINE_FEATURES.exists():
        warnings.append("Baseline moneyline features file missing; enhanced merged output was skipped.")
        return {"enhanced_rows_written": 0, "enhanced_output_csv": None}

    with BASE_MONEYLINE_FEATURES.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        base_rows = list(reader)
        base_columns = reader.fieldnames or []

    pitcher_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in pitcher_rows:
        key = (str(row.get("game_id") or ""), str(row.get("season") or ""))
        pitcher_index[key] = row

    merged_columns = list(base_columns)
    for column in PITCHER_FEATURE_COLUMNS:
        if column not in merged_columns:
            merged_columns.append(column)

    merged_rows: list[dict[str, Any]] = []
    missing_pitcher_rows = 0
    for base_row in base_rows:
        key = (str(base_row.get("game_id") or ""), str(base_row.get("season") or ""))
        pitcher_row = pitcher_index.get(key)
        if pitcher_row is None:
            missing_pitcher_rows += 1
            merged_row = dict(base_row)
            for column in PITCHER_FEATURE_COLUMNS:
                if column not in merged_row:
                    merged_row[column] = ""
        else:
            merged_row = dict(base_row)
            for column in PITCHER_FEATURE_COLUMNS:
                merged_row[column] = pitcher_row.get(column, merged_row.get(column, ""))
        merged_rows.append(merged_row)

    with ENHANCED_MONEYLINE_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=merged_columns)
        writer.writeheader()
        writer.writerows(merged_rows)

    return {
        "enhanced_rows_written": len(merged_rows),
        "enhanced_missing_pitcher_rows": missing_pitcher_rows,
        "enhanced_output_csv": str(ENHANCED_MONEYLINE_OUTPUT.relative_to(ENGINE_ROOT)),
        "enhanced_columns": merged_columns,
    }


def write_report(report: dict[str, Any]) -> None:
    with PITCHER_FEATURE_REPORT.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_pitcher_features")
    print("Building research-only starting pitcher features. No picks, odds, ROI, CLV, Telegram, or official betting actions will be created.")

    warnings: list[str] = []
    source_diagnostics: list[dict[str, Any]] = []
    files = sorted(
        path
        for path in PROCESSED_DIR.glob(INPUT_PATTERN)
        if path.name.startswith("mlb_games_") and path.name != PITCHER_FEATURE_OUTPUT.name
    )

    if not files:
        warnings.append("No processed MLB game CSV files found. Run fetch_data.py first.")
        write_report(
            {
                "status": "missing_source_data",
                "input_files_found": [],
                "total_games_read": 0,
                "completed_games_used": 0,
                "games_with_pitcher_data": 0,
                "games_with_full_pitcher_data": 0,
                "games_with_partial_pitcher_data": 0,
                "games_missing_pitcher_data": 0,
                "output_row_count": 0,
                "feature_columns": PITCHER_FEATURE_COLUMNS,
                "features_created": PITCHER_FEATURE_COLUMNS,
                "features_created_count": len(PITCHER_FEATURE_COLUMNS),
                "pitcher_data_quality_summary": {"high": 0, "medium": 0, "low": 0, "missing": 0},
                "source_diagnostics": source_diagnostics,
                "warnings": warnings,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        print(warnings[0])
        return

    games, total_read, malformed = read_games(files)
    seasons = sorted({row["_season_int"] for row in games})
    season_pitcher_payloads: dict[int, dict[str, Any] | None] = {}
    season_pitcher_maps: dict[int, dict[tuple[int, str], dict[str, dict[str, Any] | None]]] = {}

    for season in seasons:
        payload = load_pitcher_payload(season, warnings, source_diagnostics)
        season_pitcher_payloads[season] = payload
        season_pitcher_maps[season] = extract_pitcher_map(payload, season) if payload else {}

    pitcher_rows: list[dict[str, Any]] = []
    games_with_pitcher_data = 0
    games_with_full_pitcher_data = 0
    games_with_partial_pitcher_data = 0
    games_missing_pitcher_data = 0
    quality_summary: Counter[str] = Counter()
    no_prior_home = 0
    no_prior_away = 0

    histories: dict[tuple[int, str], PitcherSeasonHistory] = {}

    for row in games:
        if not is_completed(row):
            continue

        season = row["_season_int"]
        game_id = str(row.get("game_id") or "")
        key = (season, game_id)
        pitcher_entry = season_pitcher_maps.get(season, {}).get(key)

        home_team = str(row.get("home_team") or "")
        away_team = str(row.get("away_team") or "")
        game_date = row["_parsed_game_date"]
        home_score = row["_home_score_int"]
        away_score = row["_away_score_int"]
        home_won = home_score is not None and away_score is not None and home_score > away_score
        away_won = home_score is not None and away_score is not None and away_score > home_score

        def get_history(pitcher_id: str | None) -> PitcherSeasonHistory | None:
            if not pitcher_id:
                return None
            history_key = (season, pitcher_id)
            if history_key not in histories:
                histories[history_key] = PitcherSeasonHistory()
            return histories[history_key]

        home_pitcher = pitcher_entry.get("home") if pitcher_entry else None
        away_pitcher = pitcher_entry.get("away") if pitcher_entry else None
        home_history = get_history(home_pitcher.get("pitcher_id") if home_pitcher else None)
        away_history = get_history(away_pitcher.get("pitcher_id") if away_pitcher else None)

        if home_history and home_history.starts == 0:
            no_prior_home += 1
        if away_history and away_history.starts == 0:
            no_prior_away += 1

        pitcher_rows.append(build_row(row, pitcher_entry, home_history, away_history))

        if home_pitcher or away_pitcher:
          games_with_pitcher_data += 1
        if home_pitcher and away_pitcher:
            games_with_full_pitcher_data += 1
        elif home_pitcher or away_pitcher:
            games_with_partial_pitcher_data += 1
        else:
            games_missing_pitcher_data += 1

        quality_summary[pitcher_rows[-1]["pitcher_data_quality"]] += 1

        if home_history and home_pitcher and home_score is not None and away_score is not None:
            home_history.record_start(game_date, int(away_score), home_won)
        if away_history and away_pitcher and home_score is not None and away_score is not None:
            away_history.record_start(game_date, int(home_score), away_won)

    if malformed:
        warnings.append(f"Skipped {malformed} malformed rows with missing/invalid season or game_date.")
    if no_prior_home or no_prior_away:
        warnings.append("Early pitcher rows can have empty rolling-history fields until prior starts exist.")
    if games_missing_pitcher_data:
        warnings.append("Some games are missing starting pitcher data; those rows were kept with null pitcher fields.")
    if 2026 in seasons:
        warnings.append("2026 is season-to-date only; pitcher features are research-only and should not be treated as finalized model inputs yet.")

    write_pitcher_csv(pitcher_rows)
    merge_summary = merge_with_moneyline_features(pitcher_rows, warnings)

    quality_summary_dict = {
        "high": quality_summary.get("high", 0),
        "medium": quality_summary.get("medium", 0),
        "low": quality_summary.get("low", 0),
        "missing": quality_summary.get("missing", 0),
    }
    if games_with_pitcher_data == 0:
        status = "missing"
    elif games_missing_pitcher_data > 0:
        status = "partial"
    else:
        status = "available"

    report = {
        "status": status,
        "input_files_found": [str(path.relative_to(ENGINE_ROOT)) for path in files],
        "seasons_included": seasons,
        "total_games_read": total_read,
        "completed_games_used": len(pitcher_rows),
        "games_with_pitcher_data": games_with_pitcher_data,
        "games_with_full_pitcher_data": games_with_full_pitcher_data,
        "games_with_partial_pitcher_data": games_with_partial_pitcher_data,
        "games_missing_pitcher_data": games_missing_pitcher_data,
        "output_row_count": len(pitcher_rows),
        "feature_columns": PITCHER_FEATURE_COLUMNS,
        "features_created": PITCHER_FEATURE_COLUMNS,
        "features_created_count": len(PITCHER_FEATURE_COLUMNS),
        "pitcher_data_quality_summary": quality_summary_dict,
        "source_diagnostics": source_diagnostics,
        "merged_enhanced_output": merge_summary,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_report(report)

    print("Pitcher feature build completed.")
    print(f"- input files: {len(files)}")
    print(f"- total games read: {total_read}")
    print(f"- completed games used: {len(pitcher_rows)}")
    print(f"- games with pitcher data: {games_with_pitcher_data}")
    print(f"- games missing pitcher data: {games_missing_pitcher_data}")
    print(f"- output CSV: {PITCHER_FEATURE_OUTPUT}")
    print(f"- report JSON: {PITCHER_FEATURE_REPORT}")
    if merge_summary.get("enhanced_output_csv"):
        print(f"- enhanced moneyline CSV: {merge_summary['enhanced_output_csv']}")
    for warning in warnings:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
