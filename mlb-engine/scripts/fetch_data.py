"""Fetch real MLB schedule/results data for ASTRODDS.

Uses the public MLB StatsAPI schedule endpoint. This script does not create fake
picks, odds, confidence, ROI, CLV, calibration, or model outputs.
"""
from __future__ import annotations

import argparse
import csv
import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ENGINE_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ENGINE_ROOT / "data" / "raw"
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"
MODELS_DIR = ENGINE_ROOT / "models"
OUTPUTS_DIR = ENGINE_ROOT / "outputs"
CALIBRATION_DIR = ENGINE_ROOT / "calibration"

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
SUPPORTED_YEARS = set(range(2016, 2027))
CSV_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "game_type",
    "status",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "winner",
    "home_win",
    "away_win",
    "venue",
    "doubleheader",
    "game_number",
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
    for path in [RAW_DIR, PROCESSED_DIR, MODELS_DIR, OUTPUTS_DIR, CALIBRATION_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def season_date_range(year: int) -> tuple[str, str]:
    return f"{year}-01-01", f"{year}-12-31"


def build_schedule_url(year: int) -> str:
    start_date, end_date = season_date_range(year)
    query = urlencode(
        {
            "sportId": 1,
            "season": year,
            "gameType": "R",
            "startDate": start_date,
            "endDate": end_date,
            "hydrate": "team,venue,linescore",
        }
    )
    return f"{MLB_SCHEDULE_URL}?{query}"


def fetch_json(url: str, timeout_seconds: float, max_retries: int) -> tuple[dict[str, Any] | None, FetchDiagnostics]:
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
                    source_label="MLB StatsAPI",
                    endpoint_label="schedule",
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
        except Exception as error:  # Keeps CLI fail-soft without dumping stack traces.
            last_error = f"Unexpected fetch error: {error}"

    return None, FetchDiagnostics(
        source_label="MLB StatsAPI",
        endpoint_label="schedule",
        status="FAILED",
        http_status=last_status,
        timeout=timed_out,
        sanitized_url=sanitized,
        error_message=last_error or "Unknown fetch failure",
        retry_count=max_retries,
    )


def team_name(game: dict[str, Any], side: str) -> str:
    team = game.get("teams", {}).get(side, {}).get("team", {})
    return str(team.get("name") or "")


def score_value(game: dict[str, Any], side: str) -> int | None:
    score = game.get("teams", {}).get(side, {}).get("score")
    if isinstance(score, int):
        return score
    if isinstance(score, float) and score.is_integer():
        return int(score)
    return None


def game_status(game: dict[str, Any]) -> str:
    status = game.get("status", {})
    return str(status.get("detailedState") or status.get("abstractGameState") or "")


def is_final(game: dict[str, Any]) -> bool:
    status = game.get("status", {})
    detailed = str(status.get("detailedState") or "").lower()
    abstract = str(status.get("abstractGameState") or "").lower()
    return abstract == "final" or "final" in detailed


def normalize_game(game: dict[str, Any], season: int) -> dict[str, Any]:
    home_team = team_name(game, "home")
    away_team = team_name(game, "away")
    home_score = score_value(game, "home")
    away_score = score_value(game, "away")
    winner = ""
    home_win = ""
    away_win = ""

    if is_final(game) and home_score is not None and away_score is not None:
        if home_score > away_score:
            winner = home_team
            home_win = 1
            away_win = 0
        elif away_score > home_score:
            winner = away_team
            home_win = 0
            away_win = 1

    venue = game.get("venue", {})

    return {
        "game_id": game.get("gamePk") or "",
        "game_date": game.get("gameDate") or "",
        "season": season,
        "game_type": game.get("gameType") or "",
        "status": game_status(game),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score if home_score is not None else "",
        "away_score": away_score if away_score is not None else "",
        "winner": winner,
        "home_win": home_win,
        "away_win": away_win,
        "venue": venue.get("name") or "",
        "doubleheader": game.get("doubleHeader") or "",
        "game_number": game.get("gameNumber") or "",
    }


def normalize_schedule(payload: dict[str, Any], season: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_block in payload.get("dates", []):
        if not isinstance(date_block, dict):
            continue
        games = date_block.get("games", [])
        if not isinstance(games, list):
            continue
        for game in games:
            if isinstance(game, dict):
                rows.append(normalize_game(game, season))
    return rows


def write_raw(payload: dict[str, Any], year: int) -> Path:
    path = RAW_DIR / f"mlb_schedule_{year}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return path


def write_processed_csv(rows: list[dict[str, Any]], year: int) -> Path:
    path = PROCESSED_DIR / f"mlb_games_{year}.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_diagnostics(diagnostics: FetchDiagnostics) -> None:
    print("Source diagnostics:")
    for key, value in asdict(diagnostics).items():
        print(f"- {key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch regular-season MLB schedule/results data for ASTRODDS.")
    parser.add_argument(
        "--year",
        type=int,
        choices=sorted(SUPPORTED_YEARS),
        help="Season year to fetch: 2016 through 2026 (2026 is season-to-date only).",
    )
    parser.add_argument("--timeout", type=float, default=25.0, help="HTTP timeout in seconds. Default: 25.")
    parser.add_argument("--retries", type=int, default=1, help="Retry count after the first attempt. Default: 1.")
    return parser.parse_args()


def main() -> None:
    ensure_dirs()
    args = parse_args()
    print("ASTRODDS MLB Engine - fetch_data")
    print("Market focus: moneyline/game winner first; total_runs future secondary; runline disabled.")
    print("No fake picks, odds, ROI, CLV, confidence, calibration, or model output will be created.")

    if args.year is None:
        print("No --year provided. Example: python mlb-engine/scripts/fetch_data.py --year 2024")
        print("Supported years: 2016 through 2026 (2026 is season-to-date).")
        return

    if args.year == 2026:
        print("Note: 2026 is treated as season-to-date/live paper calibration data, not a completed full-season training set.")

    url = build_schedule_url(args.year)
    payload, diagnostics = fetch_json(url, timeout_seconds=args.timeout, max_retries=max(0, args.retries))
    print_diagnostics(diagnostics)

    if payload is None:
        print("Fetch failed safely. No raw or processed MLB files were written.")
        return

    rows = normalize_schedule(payload, args.year)
    raw_path = write_raw(payload, args.year)
    csv_path = write_processed_csv(rows, args.year)
    final_rows = sum(1 for row in rows if row["winner"])
    unresolved_rows = len(rows) - final_rows

    print("Fetch completed.")
    print(f"- games normalized: {len(rows)}")
    print(f"- final games with winner: {final_rows}")
    print(f"- scheduled/incomplete/no-result rows: {unresolved_rows}")
    print(f"- raw JSON: {raw_path}")
    print(f"- processed CSV: {csv_path}")
    print("Next: build verified moneyline features from processed CSV data. No model was trained here.")


if __name__ == "__main__":
    main()
