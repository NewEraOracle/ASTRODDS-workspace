"""Build safe weather / ballpark feature rows for ASTRODDS MLB Engine.

This is a research-only feature layer. It preserves venue context and optional
static roof context, but it does not invent weather, ballpark factors, picks,
odds, ROI, CLV, calibration, or official betting outputs.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_features import csv_value, parse_date, read_games, round_float

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
WEATHER_BALLPARK_OUTPUT = PROCESSED_DIR / "mlb_weather_ballpark_features.csv"
WEATHER_BALLPARK_REPORT = PROCESSED_DIR / "mlb_weather_ballpark_features_report.json"
MERGED_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_weather_ballpark.csv"
PITCHER_BULLPEN_WEATHER_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen_weather.csv"
BASE_MONEYLINE_FEATURES = PROCESSED_DIR / "mlb_moneyline_features.csv"
PITCHER_BULLPEN_FEATURES = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen.csv"
INPUT_PATTERN = "mlb_games_*.csv"

WEATHER_BALLPARK_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "venue_name",
    "venue_id",
    "ballpark_id",
    "ballpark_factor_available",
    "ballpark_run_factor",
    "ballpark_hr_factor",
    "roof_type",
    "indoor_or_dome",
    "weather_available",
    "temperature",
    "wind_speed",
    "wind_direction",
    "precipitation_risk",
    "humidity",
    "weather_risk",
    "run_environment_score",
    "weather_ballpark_data_quality",
    "weather_ballpark_warnings",
]

STATIC_BALLPARK_CONTEXT: dict[str, dict[str, Any]] = {
    "chase field": {"roof_type": "retractable", "indoor_or_dome": True},
    "globe life field": {"roof_type": "retractable", "indoor_or_dome": True},
    "loandepot park": {"roof_type": "retractable", "indoor_or_dome": True},
    "marlins park": {"roof_type": "retractable", "indoor_or_dome": True},
    "minute maid park": {"roof_type": "retractable", "indoor_or_dome": True},
    "daikin park": {"roof_type": "retractable", "indoor_or_dome": True},
    "rogers centre": {"roof_type": "retractable", "indoor_or_dome": True},
    "t-mobile park": {"roof_type": "retractable", "indoor_or_dome": True},
    "american family field": {"roof_type": "retractable", "indoor_or_dome": True},
    "tropicana field": {"roof_type": "dome", "indoor_or_dome": True},
}


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


def normalize_key(value: str | None) -> str:
    return " ".join((value or "").lower().replace("&", " and ").split())


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
        payload = json.loads(raw)
        return payload if is_record(payload) else None
    except Exception:
        return None


def input_files() -> list[Path]:
    return sorted(
        path
        for path in PROCESSED_DIR.glob(INPUT_PATTERN)
        if path.name.startswith("mlb_games_") and path.name != WEATHER_BALLPARK_OUTPUT.name
    )


def year_from_path(path: Path) -> int | None:
    try:
        return int(path.stem.split("_")[-1])
    except ValueError:
        return None


def extract_venue_map(year: int, warnings: list[str]) -> dict[tuple[int, str], dict[str, Any]]:
    raw_path = RAW_DIR / f"mlb_schedule_{year}.json"
    payload = load_json_file(raw_path)
    if payload is None:
        warnings.append(f"Year {year}: raw schedule snapshot missing or unreadable for venue enrichment.")
        return {}

    venue_map: dict[tuple[int, str], dict[str, Any]] = {}
    for date_block in payload.get("dates", []):
        if not is_record(date_block):
            continue
        for game in date_block.get("games", []):
            if not is_record(game):
                continue
            game_id = optional_string(game.get("gamePk"))
            if not game_id:
                continue
            venue = game.get("venue") if is_record(game.get("venue")) else {}
            venue_id = optional_string(venue.get("id")) if is_record(venue) else None
            venue_name = optional_string(venue.get("name")) if is_record(venue) else None
            venue_map[(year, game_id)] = {
                "venue_id": venue_id,
                "venue_name": venue_name,
            }
    return venue_map


def ballpark_context(venue_name: str | None) -> dict[str, Any]:
    normalized = normalize_key(venue_name)
    return STATIC_BALLPARK_CONTEXT.get(normalized, {})


def quality_for_row(
    venue_name: str | None,
    roof_type: str | None,
    weather_available: bool,
    ballpark_factor_available: bool,
) -> str:
    if not venue_name:
        return "missing"
    if weather_available and ballpark_factor_available:
        return "high"
    if roof_type:
        return "medium"
    return "low"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def merge_with_moneyline_features(source_csv: Path, output_csv: Path, weather_rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    if not source_csv.exists():
        warnings.append(f"Weather merge skipped because {source_csv.name} is missing.")
        return {
            "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
            "enhanced_rows_written": 0,
            "enhanced_missing_weather_rows": 0,
            "enhanced_output_csv": None,
            "enhanced_columns": [],
        }

    with source_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        base_rows = list(reader)
        base_columns = reader.fieldnames or []

    weather_index = {(str(row.get("game_id") or ""), str(row.get("season") or "")): row for row in weather_rows}

    merged_columns = list(base_columns)
    for column in WEATHER_BALLPARK_COLUMNS:
        if column not in merged_columns:
            merged_columns.append(column)

    merged_rows: list[dict[str, Any]] = []
    missing_weather_rows = 0
    for base_row in base_rows:
        key = (str(base_row.get("game_id") or ""), str(base_row.get("season") or ""))
        weather_row = weather_index.get(key)
        merged_row = dict(base_row)
        for column in WEATHER_BALLPARK_COLUMNS:
            merged_row[column] = weather_row.get(column, "") if weather_row else ""
        if weather_row is None:
            missing_weather_rows += 1
        merged_rows.append(merged_row)

    write_csv(output_csv, merged_rows, merged_columns)
    return {
        "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
        "enhanced_rows_written": len(merged_rows),
        "enhanced_missing_weather_rows": missing_weather_rows,
        "enhanced_output_csv": str(output_csv.relative_to(ENGINE_ROOT)),
        "enhanced_columns": merged_columns,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_weather_ballpark_features")
    print("Building research-only weather / ballpark context features. No picks, odds, ROI, CLV, calibration, Telegram, or official betting actions will be created.")

    warnings: list[str] = []
    files = input_files()
    if not files:
        warnings.append("No processed MLB game CSV files found. Run fetch_data.py first.")
        write_json(
            WEATHER_BALLPARK_REPORT,
            {
                "status": "missing_source_data",
                "input_files_found": [],
                "games_read": 0,
                "games_with_venue_data": 0,
                "games_with_weather_data": 0,
                "games_missing_weather_data": 0,
                "games_with_ballpark_factor_data": 0,
                "features_created": 0,
                "feature_columns": WEATHER_BALLPARK_COLUMNS,
                "data_quality_summary": {"high": 0, "medium": 0, "low": 0, "missing": 0},
                "warnings": warnings,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(warnings[0])
        return

    games, total_read, malformed = read_games(files)
    seasons = sorted({row["_season_int"] for row in games})
    venue_maps = {season: extract_venue_map(season, warnings) for season in seasons}

    output_rows: list[dict[str, Any]] = []
    quality_counts: Counter[str] = Counter()
    games_with_venue_data = 0
    games_with_weather_data = 0
    games_missing_weather_data = 0
    games_with_ballpark_factor_data = 0

    for row in games:
        season = row["_season_int"]
        game_id = str(row.get("game_id") or "")
        venue_info = venue_maps.get(season, {}).get((season, game_id), {})
        venue_name = optional_string(venue_info.get("venue_name")) or optional_string(row.get("venue"))
        venue_id = optional_string(venue_info.get("venue_id"))
        context = ballpark_context(venue_name)
        roof_type = optional_string(context.get("roof_type"))
        indoor_or_dome = context.get("indoor_or_dome")
        weather_available = False
        ballpark_factor_available = False

        if venue_name:
            games_with_venue_data += 1
        if weather_available:
            games_with_weather_data += 1
        else:
            games_missing_weather_data += 1
        if ballpark_factor_available:
            games_with_ballpark_factor_data += 1

        quality = quality_for_row(venue_name, roof_type, weather_available, ballpark_factor_available)
        quality_counts[quality] += 1

        row_warnings: list[str] = []
        if not weather_available:
            row_warnings.append("Historical weather unavailable from saved MLB schedule snapshots; weather fields are null.")
        if roof_type:
            row_warnings.append("Static roof context applied from a small documented venue map.")
        else:
            row_warnings.append("No static ballpark factor mapping for this venue; ballpark factors remain null.")
        if not venue_name:
            row_warnings.append("Venue data unavailable for this row.")

        output_rows.append(
            {
                "game_id": game_id,
                "game_date": row.get("game_date") or "",
                "season": row.get("season") or "",
                "home_team": row.get("home_team") or "",
                "away_team": row.get("away_team") or "",
                "venue_name": venue_name or "",
                "venue_id": venue_id or "",
                "ballpark_id": venue_id or "",
                "ballpark_factor_available": csv_value(ballpark_factor_available),
                "ballpark_run_factor": "",
                "ballpark_hr_factor": "",
                "roof_type": roof_type or "",
                "indoor_or_dome": csv_value(indoor_or_dome if indoor_or_dome is not None else None),
                "weather_available": csv_value(weather_available),
                "temperature": "",
                "wind_speed": "",
                "wind_direction": "",
                "precipitation_risk": "",
                "humidity": "",
                "weather_risk": "",
                "run_environment_score": "",
                "weather_ballpark_data_quality": quality,
                "weather_ballpark_warnings": " | ".join(dict.fromkeys(row_warnings)),
            }
        )

    if malformed:
        warnings.append(f"Skipped {malformed} malformed rows with missing/invalid season or game_date.")
    if games_missing_weather_data:
        warnings.append("Historical weather data is not present in the saved MLB schedule snapshots; weather fields remain null.")
    if games_with_ballpark_factor_data == 0:
        warnings.append("No static ballpark run/hr factor mapping has been enabled yet; factor fields remain null.")
    if 2026 in seasons:
        warnings.append("2026 is season-to-date only; weather/ballpark features remain research-only and should not be treated as finalized model inputs yet.")
    warnings.append("Weather / ballpark context is research only and does not change official picks, Strong Buys, Telegram alerts, or real-money behavior.")

    write_csv(WEATHER_BALLPARK_OUTPUT, output_rows, WEATHER_BALLPARK_COLUMNS)
    merged_summary = merge_with_moneyline_features(BASE_MONEYLINE_FEATURES, MERGED_OUTPUT, output_rows, warnings)
    pitcher_bullpen_weather_summary = merge_with_moneyline_features(PITCHER_BULLPEN_FEATURES, PITCHER_BULLPEN_WEATHER_OUTPUT, output_rows, warnings)

    report = {
        "status": "available" if games_with_venue_data else "missing",
        "input_files_found": [str(path.relative_to(ENGINE_ROOT)) for path in files],
        "seasons_included": seasons,
        "games_read": total_read,
        "games_with_venue_data": games_with_venue_data,
        "games_with_weather_data": games_with_weather_data,
        "games_missing_weather_data": games_missing_weather_data,
        "games_with_ballpark_factor_data": games_with_ballpark_factor_data,
        "features_created": len(output_rows),
        "feature_columns": WEATHER_BALLPARK_COLUMNS,
        "data_quality_summary": {
            "high": quality_counts.get("high", 0),
            "medium": quality_counts.get("medium", 0),
            "low": quality_counts.get("low", 0),
            "missing": quality_counts.get("missing", 0),
        },
        "merged_enhanced_output": merged_summary,
        "merged_pitcher_bullpen_weather_output": pitcher_bullpen_weather_summary,
        "warnings": list(dict.fromkeys(warnings)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(WEATHER_BALLPARK_REPORT, report)

    print("Weather / ballpark feature build completed.")
    print(f"- input files: {len(files)}")
    print(f"- games read: {total_read}")
    print(f"- games with venue data: {games_with_venue_data}")
    print(f"- games with weather data: {games_with_weather_data}")
    print(f"- games missing weather data: {games_missing_weather_data}")
    print(f"- games with ballpark factor data: {games_with_ballpark_factor_data}")
    print(f"- output CSV: {WEATHER_BALLPARK_OUTPUT}")
    print(f"- report JSON: {WEATHER_BALLPARK_REPORT}")
    if merged_summary.get("enhanced_output_csv"):
        print(f"- merged moneyline CSV: {merged_summary['enhanced_output_csv']}")
    if pitcher_bullpen_weather_summary.get("enhanced_output_csv"):
        print(f"- merged pitcher+bullpen+weather CSV: {pitcher_bullpen_weather_summary['enhanced_output_csv']}")
    for warning in report["warnings"]:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
