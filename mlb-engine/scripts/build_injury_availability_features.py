"""Build safe MLB injury / player availability research features for ASTRODDS.

This layer is research-only. It never creates picks, odds, ROI, CLV,
calibration, or official betting outputs. It uses public MLB StatsAPI roster
injured-list data when available and fails soft when the source is missing.
"""
from __future__ import annotations

import argparse
import csv
import json
import socket
import ssl
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"

STANDALONE_OUTPUT = PROCESSED_DIR / "mlb_injury_availability_features.csv"
REPORT_OUTPUT = PROCESSED_DIR / "mlb_injury_availability_features_report.json"
MERGED_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_injuries.csv"
MERGED_RICH_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv"

YEAR_RANGE = list(range(2016, 2027))
BASE_GAME_FILES = [PROCESSED_DIR / f"mlb_games_{year}.csv" for year in YEAR_RANGE]
BASE_FEATURE_FILE = PROCESSED_DIR / "mlb_moneyline_features.csv"

INJURY_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_injury_data_available",
    "away_injury_data_available",
    "home_players_on_il_count",
    "away_players_on_il_count",
    "home_key_players_unavailable_count",
    "away_key_players_unavailable_count",
    "home_pitcher_availability_risk",
    "away_pitcher_availability_risk",
    "home_bullpen_availability_risk",
    "away_bullpen_availability_risk",
    "home_lineup_availability_risk",
    "away_lineup_availability_risk",
    "home_injury_risk_score",
    "away_injury_risk_score",
    "injury_data_quality",
    "injury_source",
    "injury_warnings",
]


@dataclass
class FetchDiagnostics:
  source_label: str
  endpoint_label: str
  status: str
  http_status: int | None
  timeout: bool
  sanitized_url: str
  error_message: str | None
  retry_count: int


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def is_record(value: Any) -> bool:
    return isinstance(value, dict)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.strip().lower().replace(".", "").split())
    return normalize_text(str(value))


def optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def optional_int(value: Any) -> int | None:
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


def clamp01(value: float) -> float:
    if value != value:
        return 0.0
    return max(0.0, min(1.0, value))


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def unique_strings(values: list[str | None]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_base_rows() -> tuple[list[dict[str, str]], Path | None]:
    if BASE_FEATURE_FILE.exists():
        return read_csv_rows(BASE_FEATURE_FILE), BASE_FEATURE_FILE

    existing_game_files = [path for path in BASE_GAME_FILES if path.exists()]
    if not existing_game_files:
        return [], None

    rows: list[dict[str, str]] = []
    for path in existing_game_files:
        rows.extend(read_csv_rows(path))
    return rows, None


def load_game_rows_by_year() -> tuple[list[dict[str, str]], dict[int, int], list[int], list[str]]:
    rows: list[dict[str, str]] = []
    games_read_by_year: dict[int, int] = {}
    years_included: list[int] = []
    warnings: list[str] = []

    for year in YEAR_RANGE:
        path = PROCESSED_DIR / f"mlb_games_{year}.csv"
        if not path.exists():
            warnings.append(f"Processed MLB game file missing for {year}: {path.name}.")
            continue
        try:
            year_rows = read_csv_rows(path)
        except Exception as error:
            warnings.append(f"Processed MLB game file unreadable for {year}: {error}.")
            continue
        games_read_by_year[year] = len(year_rows)
        years_included.append(year)
        rows.extend(year_rows)

    return rows, games_read_by_year, years_included, warnings


def is_completed_game_row(row: dict[str, str]) -> bool:
    home_score = optional_int(row.get("home_score"))
    away_score = optional_int(row.get("away_score"))
    if home_score is None or away_score is None:
        return False

    status = normalize_text(row.get("status"))
    if not status:
        return True
    if any(token in status for token in ("final", "completed", "game over", "official", "extra innings")):
        return True
    return True


def load_raw_schedule_games() -> dict[str, dict[str, Any]]:
    games: dict[str, dict[str, Any]] = {}
    for year in range(2016, 2027):
        path = RAW_DIR / f"mlb_schedule_{year}.json"
        if not path.exists():
          continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8").replace("\ufeff", ""))
        except Exception:
            continue
        if not is_record(payload):
            continue
        for date_block in payload.get("dates", []):
            if not is_record(date_block):
                continue
            for game in date_block.get("games", []):
                if not is_record(game):
                    continue
                game_pk = game.get("gamePk")
                if game_pk is None:
                    continue
                games[str(game_pk)] = game
    return games


def build_schedule_url(year: int) -> str:
    query = urlencode(
        {
            "sportId": 1,
            "season": year,
            "gameType": "R",
            "startDate": f"{year}-01-01",
            "endDate": f"{year}-12-31",
            "hydrate": "team,venue,linescore,probablePitcher",
        }
    )
    return f"https://statsapi.mlb.com/api/v1/schedule?{query}"


def build_teams_url(year: int) -> str:
    query = urlencode({"sportId": 1, "season": year})
    return f"https://statsapi.mlb.com/api/v1/teams?{query}"


def build_roster_url(team_id: int, year: int) -> str:
    query = urlencode({"rosterType": "injuredList", "season": year})
    return f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?{query}"


def fetch_json(
    url: str,
    timeout_seconds: float,
    max_retries: int,
    source_label: str,
    endpoint_label: str,
) -> tuple[dict[str, Any] | None, FetchDiagnostics]:
    sanitized = sanitize_url(url)
    attempts = max(1, max_retries + 1)
    last_error: str | None = None
    last_status: int | None = None
    timed_out = False

    for attempt in range(attempts):
        request = Request(url, headers={"User-Agent": "ASTRODDS-MLB-Engine/0.1"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(getattr(response, "status", 200))
                raw = response.read().decode("utf-8")
                payload = json.loads(raw)
                return payload, FetchDiagnostics(
                    source_label=source_label,
                    endpoint_label=endpoint_label,
                    status="CONNECTED",
                    http_status=status_code,
                    timeout=False,
                    sanitized_url=sanitized,
                    error_message=None,
                    retry_count=attempt,
                )
        except HTTPError as error:
            last_status = error.code
            last_error = f"HTTP {error.code}: {error.reason}"
        except (TimeoutError, socket.timeout) as error:
            timed_out = True
            last_error = f"Timeout after {timeout_seconds}s: {error}"
        except URLError as error:
            reason = getattr(error, "reason", error)
            timed_out = isinstance(reason, socket.timeout)
            last_error = f"URL error: {reason}"
        except json.JSONDecodeError as error:
            last_error = f"Invalid JSON response: {error}"
        except Exception as error:  # keep fail-soft
            last_error = f"Unexpected fetch error: {error}"

    return None, FetchDiagnostics(
        source_label=source_label,
        endpoint_label=endpoint_label,
        status="FAILED",
        http_status=last_status,
        timeout=timed_out,
        sanitized_url=sanitized,
        error_message=last_error or "Unknown fetch failure",
        retry_count=max_retries,
    )


def parse_team_name(value: Any) -> str:
    return optional_string(value) or ""


def status_from_text(text: str | None) -> str:
    normalized = normalize_text(text)
    if not normalized or "not connected" in normalized or "unavailable" in normalized or "missing" in normalized:
        return "missing"
    if "projected" in normalized or "partial" in normalized or "probable" in normalized:
        return "projected"
    if "confirmed" in normalized or "available" in normalized:
        return "confirmed"
    return "projected"


def risk_from_status(status: str, missing_value: float = 0.68) -> float:
    if status == "confirmed":
        return 0.18
    if status == "projected":
        return 0.45
    return missing_value


def parse_team_roster_snapshot(payload: dict[str, Any] | None, source_url: str, season: int, team_name: str) -> dict[str, Any]:
    if not is_record(payload):
        return {
            "available": False,
            "players_on_il_count": 0,
            "pitcher_il_count": 0,
            "hitter_il_count": 0,
            "key_players_unavailable_count": 0,
            "warnings": [f"{team_name} injured-list roster unavailable for {season}."],
            "source_url": source_url,
        }

    roster = payload.get("roster", [])
    if not isinstance(roster, list):
        roster = []

    players_on_il = 0
    pitcher_il = 0
    hitter_il = 0

    for player in roster:
        if not is_record(player):
            continue
        players_on_il += 1
        position = player.get("position") if is_record(player.get("position")) else {}
        abbreviation = normalize_text(position.get("abbreviation") if is_record(position) else None)
        role = normalize_text(position.get("name") if is_record(position) else None)
        if abbreviation in {"p", "sp", "rp"} or "pitcher" in role:
            pitcher_il += 1
        else:
            hitter_il += 1

    warnings = [
        f"Public injured-list roster returned {players_on_il} player{'' if players_on_il == 1 else 's'} for {team_name} in {season}.",
        "Public injured-list roster is a conservative availability proxy; player importance is not authoritative.",
    ]

    return {
        "available": True,
        "players_on_il_count": players_on_il,
        "pitcher_il_count": pitcher_il,
        "hitter_il_count": hitter_il,
        "key_players_unavailable_count": players_on_il,
        "warnings": warnings,
        "source_url": source_url,
    }


def build_team_id_lookup(team_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if not is_record(team_payload):
        return lookup
    teams = team_payload.get("teams", [])
    if not isinstance(teams, list):
        return lookup
    for team in teams:
        if not is_record(team):
            continue
        team_id = optional_int(team.get("id"))
        if team_id is None:
            continue
        names = [
            team.get("name"),
            team.get("teamName"),
            team.get("clubName"),
            team.get("fullName"),
            team.get("locationName"),
            team.get("franchiseName"),
            team.get("abbreviation"),
        ]
        for name in names:
            normalized = normalize_text(name)
            if normalized and normalized not in lookup:
                lookup[normalized] = {"id": team_id, "name": parse_team_name(team.get("fullName") or team.get("name") or name)}
    return lookup


def pick_team_id(team_name: str, lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    normalized = normalize_text(team_name)
    if not normalized:
        return None
    if normalized in lookup:
        return lookup[normalized]
    for alias, entry in lookup.items():
        if alias in normalized or normalized in alias:
            return entry
    return None


def team_injury_snapshot(
    season: int,
    team_name: str,
    team_lookup: dict[str, dict[str, Any]],
    timeout_seconds: float,
    max_retries: int,
    diagnostics: list[FetchDiagnostics],
    roster_cache: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    team_entry = pick_team_id(team_name, team_lookup)
    if not team_entry:
        return {
            "available": False,
            "players_on_il_count": 0,
            "pitcher_il_count": 0,
            "hitter_il_count": 0,
            "key_players_unavailable_count": 0,
            "warnings": [f"{team_name} team ID could not be resolved for {season}."],
            "source_url": "",
        }

    cache_key = (season, int(team_entry["id"]))
    if cache_key in roster_cache:
        return roster_cache[cache_key]

    roster_url = build_roster_url(int(team_entry["id"]), season)
    payload, fetch_diag = fetch_json(
        roster_url,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        source_label="MLB StatsAPI",
        endpoint_label="injuredList roster",
    )
    diagnostics.append(fetch_diag)
    if payload is None:
        snapshot = {
            "available": False,
            "players_on_il_count": 0,
            "pitcher_il_count": 0,
            "hitter_il_count": 0,
            "key_players_unavailable_count": 0,
            "warnings": [f"{team_name} injured-list roster fetch failed for {season}."],
            "source_url": roster_url,
        }
    else:
        snapshot = parse_team_roster_snapshot(payload, roster_url, season, team_name)

    roster_cache[cache_key] = snapshot
    return snapshot


def team_injury_risk(
    snapshot: dict[str, Any],
    lineup_status: str,
    pitcher_status: str,
    bullpen_risk: float | None,
    game_has_probable_pitcher: bool,
) -> tuple[float, float, float, float]:
    data_available = bool(snapshot.get("available"))
    players_on_il = optional_int(snapshot.get("players_on_il_count")) or 0
    pitcher_il = optional_int(snapshot.get("pitcher_il_count")) or 0
    hitter_il = optional_int(snapshot.get("hitter_il_count")) or 0

    lineup_risk = risk_from_status(lineup_status, missing_value=0.72)
    if data_available:
        lineup_risk = clamp01(0.15 + (hitter_il * 0.06) + (pitcher_il * 0.03))
    elif lineup_risk < 0.55:
        lineup_risk = 0.55

    pitcher_risk = risk_from_status(pitcher_status, missing_value=0.74)
    if data_available and game_has_probable_pitcher:
        pitcher_risk = clamp01(0.18 + (pitcher_il * 0.08))
    elif not game_has_probable_pitcher:
        pitcher_risk = max(pitcher_risk, 0.62)

    bullpen_base = bullpen_risk if bullpen_risk is not None else (0.34 + pitcher_il * 0.04)
    bullpen_risk_value = clamp01(bullpen_base)

    injury_risk = clamp01(0.35 * lineup_risk + 0.35 * pitcher_risk + 0.30 * bullpen_risk_value)
    if not data_available:
        injury_risk = clamp01(max(injury_risk, 0.58))

    if players_on_il > 4:
        injury_risk = clamp01(injury_risk + 0.05)
    if players_on_il > 8:
        injury_risk = clamp01(injury_risk + 0.05)

    return lineup_risk, pitcher_risk, bullpen_risk_value, injury_risk


def quality_bucket(home_available: bool, away_available: bool, lineup_risk: float, pitcher_risk: float, bullpen_risk: float) -> str:
    if home_available and away_available:
        if lineup_risk <= 0.30 and pitcher_risk <= 0.30 and bullpen_risk <= 0.35:
            return "high"
        return "medium"
    if home_available or away_available:
        return "low"
    return "missing"


def read_numeric(row: dict[str, str], key: str) -> float | None:
    return optional_float(row.get(key))


def load_rows_by_game_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        game_id = (row.get("game_id") or row.get("gameId") or "").strip()
        if game_id:
            indexed[game_id] = row
    return indexed


def build_game_rows() -> tuple[list[dict[str, str]], str]:
    rows, _, _, _ = load_game_rows_by_year()
    if rows:
        return rows, "mlb_games_2016.csv..mlb_games_2026.csv"
    return [], "mlb_games_2016.csv..mlb_games_2026.csv"


def merge_injury_columns(row: dict[str, str], injury_row: dict[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    merged.update(injury_row)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Build research-only MLB injury / player availability features for ASTRODDS.")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds. Default: 20.")
    parser.add_argument("--retries", type=int, default=1, help="Retry count after the first attempt. Default: 1.")
    args = parser.parse_args()

    ensure_dirs()
    print("ASTRODDS MLB Engine - build_injury_availability_features")
    print("Research-only injury / player availability layer.")
    print("No official picks, Strong Buys, Telegram alerts, real-money trading, ROI, CLV, or betting edge will be created.")

    all_game_rows, games_read_by_year, years_included, load_warnings = load_game_rows_by_year()
    raw_games = load_raw_schedule_games()
    completed_game_rows = [row for row in all_game_rows if is_completed_game_row(row)]
    total_games_read = len(all_game_rows)
    completed_games_used = len(completed_game_rows)

    print(f"Years requested: {', '.join(str(year) for year in YEAR_RANGE)}")
    print(f"Years included: {', '.join(str(year) for year in years_included) if years_included else 'none'}")
    print(f"Total games read: {total_games_read}")
    print(f"Completed games used: {completed_games_used}")

    if not all_game_rows:
        report = {
            "status": "missing",
            "years_requested": YEAR_RANGE,
            "years_included": years_included,
            "games_read_by_year": games_read_by_year,
            "total_games_read": 0,
            "completed_games_used": 0,
            "games_read": 0,
            "games_with_injury_data": 0,
            "games_missing_injury_data": 0,
            "injury_source_used": "unavailable",
            "injury_source": "unavailable",
            "features_created": 0,
            "data_quality_summary": {
                "high": 0,
                "medium": 0,
                "low": 0,
                "missing": 0,
            },
            "warnings": [
                *load_warnings,
                "No MLB game CSVs were found for injury feature building.",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_diagnostics": [],
            "merged_outputs": {
                "injury_output_csv": str(STANDALONE_OUTPUT),
                "merged_moneyline_csv": str(MERGED_OUTPUT),
                "merged_rich_output_csv": str(MERGED_RICH_OUTPUT),
            },
            "source_file": "mlb_games_2016.csv..mlb_games_2026.csv",
        }
        REPORT_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("No game rows were available. Report written with missing status.")
        return

    seasons = sorted({optional_int(row.get("season")) for row in completed_game_rows if optional_int(row.get("season")) is not None})
    season_to_team_lookup: dict[int, dict[str, dict[str, Any]]] = {}
    fetch_diagnostics: list[FetchDiagnostics] = []
    roster_cache: dict[tuple[int, int], dict[str, Any]] = {}
    warnings: list[str] = [*load_warnings]

    for season in seasons:
        teams_url = build_teams_url(season)
        teams_payload, teams_diag = fetch_json(
            teams_url,
            timeout_seconds=args.timeout,
            max_retries=max(0, args.retries),
            source_label="MLB StatsAPI",
            endpoint_label="teams",
        )
        fetch_diagnostics.append(teams_diag)
        if teams_payload is None:
            warnings.append(f"Team lookup unavailable for {season}; injury snapshots may be missing.")
            season_to_team_lookup[season] = {}
            continue
        season_to_team_lookup[season] = build_team_id_lookup(teams_payload)
        if not season_to_team_lookup[season]:
            warnings.append(f"Team lookup returned no usable teams for {season}.")

    injured_snapshots: dict[tuple[int, str], dict[str, Any]] = {}
    injury_rows: list[dict[str, Any]] = []
    data_quality_counts = {"high": 0, "medium": 0, "low": 0, "missing": 0}
    games_with_injury_data = 0
    games_missing_injury_data = 0

    for row in completed_game_rows:
        season = optional_int(row.get("season"))
        game_id = (row.get("game_id") or "").strip()
        game_date = row.get("game_date") or ""
        home_team = row.get("home_team") or ""
        away_team = row.get("away_team") or ""
        if season is None:
            continue

        lookup = season_to_team_lookup.get(season, {})
        home_snapshot = team_injury_snapshot(season, home_team, lookup, args.timeout, max(0, args.retries), fetch_diagnostics, roster_cache)
        away_snapshot = team_injury_snapshot(season, away_team, lookup, args.timeout, max(0, args.retries), fetch_diagnostics, roster_cache)
        injured_snapshots[(season, home_team)] = home_snapshot
        injured_snapshots[(season, away_team)] = away_snapshot

        raw_game = raw_games.get(game_id)
        home_probable = raw_game and is_record(raw_game.get("teams", {}).get("home", {})) and is_record(raw_game.get("teams", {}).get("home", {}).get("probablePitcher", {}))
        away_probable = raw_game and is_record(raw_game.get("teams", {}).get("away", {})) and is_record(raw_game.get("teams", {}).get("away", {}).get("probablePitcher", {}))
        home_probable_name = None
        away_probable_name = None
        if is_record(raw_game):
            teams = raw_game.get("teams", {})
            if is_record(teams):
                home_probable_name = optional_string(teams.get("home", {}).get("probablePitcher", {}).get("fullName")) if is_record(teams.get("home", {})) and is_record(teams.get("home", {}).get("probablePitcher", {})) else None
                away_probable_name = optional_string(teams.get("away", {}).get("probablePitcher", {}).get("fullName")) if is_record(teams.get("away", {})) and is_record(teams.get("away", {}).get("probablePitcher", {})) else None

        home_lineup_status = status_from_text(row.get("home_lineup_status"))
        away_lineup_status = status_from_text(row.get("away_lineup_status"))
        home_pitcher_status = status_from_text(row.get("home_pitcher_status"))
        away_pitcher_status = status_from_text(row.get("away_pitcher_status"))
        home_bullpen_risk = read_numeric(row, "home_bullpen_risk")
        away_bullpen_risk = read_numeric(row, "away_bullpen_risk")

        home_lineup_risk, home_pitcher_risk, home_bullpen_risk_value, home_injury_risk = team_injury_risk(
            home_snapshot,
            home_lineup_status,
            home_pitcher_status,
            home_bullpen_risk,
            bool(home_probable),
        )
        away_lineup_risk, away_pitcher_risk, away_bullpen_risk_value, away_injury_risk = team_injury_risk(
            away_snapshot,
            away_lineup_status,
            away_pitcher_status,
            away_bullpen_risk,
            bool(away_probable),
        )

        home_available = bool(home_snapshot.get("available"))
        away_available = bool(away_snapshot.get("available"))
        if home_available or away_available:
            games_with_injury_data += 1
        else:
            games_missing_injury_data += 1

        quality = quality_bucket(home_available, away_available, home_lineup_risk, home_pitcher_risk, home_bullpen_risk_value)
        data_quality_counts[quality] += 1

        injury_warnings = unique_strings(
            [
                *(home_snapshot.get("warnings") or []),
                *(away_snapshot.get("warnings") or []),
                None if home_available or away_available else "Injury / player availability data unavailable.",
                "Official use blocked - research only.",
                "Public injured-list roster data is a conservative proxy; player importance is not authoritative.",
                "Lineup, bullpen, and pitcher availability are conservative risk proxies only.",
            ]
        )

        injury_rows.append(
            {
                "game_id": game_id,
                "game_date": game_date,
                "season": season,
                "home_team": home_team,
                "away_team": away_team,
                "home_injury_data_available": home_available,
                "away_injury_data_available": away_available,
                "home_players_on_il_count": home_snapshot.get("players_on_il_count", 0),
                "away_players_on_il_count": away_snapshot.get("players_on_il_count", 0),
                "home_key_players_unavailable_count": home_snapshot.get("key_players_unavailable_count", 0),
                "away_key_players_unavailable_count": away_snapshot.get("key_players_unavailable_count", 0),
                "home_pitcher_availability_risk": round(home_pitcher_risk, 4),
                "away_pitcher_availability_risk": round(away_pitcher_risk, 4),
                "home_bullpen_availability_risk": round(home_bullpen_risk_value, 4),
                "away_bullpen_availability_risk": round(away_bullpen_risk_value, 4),
                "home_lineup_availability_risk": round(home_lineup_risk, 4),
                "away_lineup_availability_risk": round(away_lineup_risk, 4),
                "home_injury_risk_score": round(home_injury_risk, 4),
                "away_injury_risk_score": round(away_injury_risk, 4),
                "injury_data_quality": quality,
                "injury_source": "MLB StatsAPI public injured-list roster data + research-only availability proxies",
                "injury_warnings": " | ".join(injury_warnings),
                "home_probable_pitcher_name": home_probable_name or "",
                "away_probable_pitcher_name": away_probable_name or "",
            }
        )

    injury_source = "MLB StatsAPI public injured-list roster data + research-only availability proxies"
    status = "missing"
    if games_with_injury_data > 0 and games_missing_injury_data > 0:
        status = "partial"
    elif games_with_injury_data > 0:
        status = "available"

    report_warnings = unique_strings(
        [
            *warnings,
            *load_warnings,
            "Injury / player availability analysis is research only and does not create official picks.",
            "Public injured-list roster data is a conservative proxy; exact key-player importance is not guaranteed.",
            "No paid or authenticated injury API is used.",
            "Official use remains blocked until a future combined risk gate is explicitly approved.",
        ]
    )
    if games_with_injury_data == 0:
        report_warnings.append("Injury / player availability data unavailable.")

    output_rows: list[dict[str, Any]] = []
    for row in injury_rows:
        output_rows.append({key: row.get(key, "") for key in INJURY_COLUMNS})

    with STANDALONE_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INJURY_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    merged_outputs: dict[str, str] = {"injury_output_csv": str(STANDALONE_OUTPUT)}
    if BASE_FEATURE_FILE.exists():
        base_rows = read_csv_rows(BASE_FEATURE_FILE)
        injury_by_game_id = {row["game_id"]: row for row in injury_rows if row.get("game_id")}
        merged_rows = []
        for base_row in base_rows:
            injury_row = injury_by_game_id.get((base_row.get("game_id") or "").strip(), {})
            merged_row = dict(base_row)
            merged_row.update(injury_row)
            merged_rows.append(merged_row)

        with MERGED_OUTPUT.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(merged_rows[0].keys()) if merged_rows else list(base_rows[0].keys()) + INJURY_COLUMNS)
            writer.writeheader()
            writer.writerows(merged_rows)
        merged_outputs["merged_moneyline_csv"] = str(MERGED_OUTPUT)

        with MERGED_RICH_OUTPUT.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(merged_rows[0].keys()) if merged_rows else list(base_rows[0].keys()) + INJURY_COLUMNS)
            writer.writeheader()
            writer.writerows(merged_rows)
        merged_outputs["merged_rich_output_csv"] = str(MERGED_RICH_OUTPUT)
    else:
        merged_outputs["merged_moneyline_csv"] = str(MERGED_OUTPUT)
        merged_outputs["merged_rich_output_csv"] = str(MERGED_RICH_OUTPUT)

    report = {
        "status": status,
        "years_requested": YEAR_RANGE,
        "years_included": years_included,
        "games_read_by_year": games_read_by_year,
        "total_games_read": total_games_read,
        "completed_games_used": completed_games_used,
        "games_read": total_games_read,
        "games_with_injury_data": games_with_injury_data,
        "games_missing_injury_data": games_missing_injury_data,
        "injury_source_used": injury_source,
        "injury_source": injury_source,
        "features_created": len(output_rows),
        "data_quality_summary": data_quality_counts,
        "injury_data_quality": status,
        "warnings": report_warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_diagnostics": [asdict(item) for item in fetch_diagnostics],
        "merged_outputs": merged_outputs,
        "source_file": "mlb_games_2016.csv..mlb_games_2026.csv",
    }

    REPORT_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Injury / availability feature build complete.")
    print(f"Games read: {total_games_read}")
    print(f"Games with injury data: {games_with_injury_data}")
    print(f"Games missing injury data: {games_missing_injury_data}")
    print(f"Output CSV: {STANDALONE_OUTPUT}")
    print(f"Report JSON: {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
