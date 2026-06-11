"""Build safe research-only lineup/player feature rows for ASTRODDS MLB Engine.

This is a conservative research layer. It does not invent confirmed lineups or
player stats. When public confirmed lineup data is unavailable, it falls back to
explicitly labeled team-level lineup proxies built from pre-game historical
offense context only.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ENGINE_ROOT / "data" / "processed"

STANDALONE_OUTPUT = PROCESSED_DIR / "mlb_lineup_player_features.csv"
REPORT_OUTPUT = PROCESSED_DIR / "mlb_lineup_player_features_report.json"
MERGED_MONEYLINE_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_lineup.csv"
MERGED_RICH_OUTPUT = PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv"

SOURCE_CANDIDATES = [
    PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen_weather.csv",
    PROCESSED_DIR / "mlb_moneyline_features_with_weather_ballpark.csv",
    PROCESSED_DIR / "mlb_moneyline_features_with_pitchers_bullpen.csv",
    PROCESSED_DIR / "mlb_moneyline_features_with_pitchers.csv",
    PROCESSED_DIR / "mlb_moneyline_features.csv",
]

LINEUP_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_lineup_status",
    "away_lineup_status",
    "home_lineup_players_count",
    "away_lineup_players_count",
    "home_top4_batters_available",
    "away_top4_batters_available",
    "home_missing_key_batters_count",
    "away_missing_key_batters_count",
    "home_lineup_obp_proxy",
    "away_lineup_obp_proxy",
    "home_lineup_slg_proxy",
    "away_lineup_slg_proxy",
    "home_lineup_strength_score",
    "away_lineup_strength_score",
    "home_lineup_downgrade_score",
    "away_lineup_downgrade_score",
    "lineup_data_quality",
    "lineup_warnings",
]


@dataclass
class LineupSideProxy:
    status: str
    players_count: int
    top4_available: int
    missing_key_batters: int
    obp_proxy: float | None
    slg_proxy: float | None
    strength_score: float
    downgrade_score: float
    warnings: list[str]


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


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if value != value:
        return minimum
    return max(minimum, min(maximum, value))


def round_float(value: float | None, digits: int = 4) -> float | str:
    if value is None:
        return ""
    return round(value, digits)


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def unique_strings(values: list[str | None]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def select_source_file() -> Path | None:
    for candidate in SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def parse_team_proxy(value: Any) -> float | None:
    return optional_float(value)


def offense_proxy_strength(row: dict[str, str], side: str) -> tuple[float | None, list[str]]:
    games_played_before = optional_number(row.get(f"{side}_games_played_before")) or 0
    runs_scored_last_10 = parse_team_proxy(row.get(f"{side}_runs_scored_last_10"))
    runs_scored_last_30 = parse_team_proxy(row.get(f"{side}_runs_scored_last_30"))
    run_diff_last_10 = parse_team_proxy(row.get(f"{side}_run_diff_last_10"))
    run_diff_last_30 = parse_team_proxy(row.get(f"{side}_run_diff_last_30"))

    warnings: list[str] = []
    if games_played_before <= 0:
        warnings.append("Lineup data unavailable before this game.")
        return None, warnings

    score = 0.5
    if runs_scored_last_10 is not None:
        score += ((runs_scored_last_10 / 10.0) - 4.3) * 0.05
    if runs_scored_last_30 is not None:
        score += ((runs_scored_last_30 / 30.0) - 4.3) * 0.03
    if run_diff_last_10 is not None:
        score += (run_diff_last_10 / 10.0) * 0.015
    if run_diff_last_30 is not None:
        score += (run_diff_last_30 / 30.0) * 0.01

    if all(value is None for value in (runs_scored_last_10, runs_scored_last_30, run_diff_last_10, run_diff_last_30)):
        warnings.append("Team-level lineup proxy unavailable from pre-game offense history.")
        return None, warnings

    return clamp(score), warnings


def build_side_proxy(row: dict[str, str], side: str) -> LineupSideProxy:
    side_label = "home" if side == "home" else "away"
    team_name = row.get(f"{side_label}_team") or ""
    strength, warnings = offense_proxy_strength(row, side_label)
    games_played_before = optional_number(row.get(f"{side_label}_games_played_before")) or 0

    if strength is None:
        warnings.append(f"{team_name or side_label.title()} lineup remains missing because no safe pre-game batting proxy was available.")
        return LineupSideProxy(
            status="missing",
            players_count=0,
            top4_available=0,
            missing_key_batters=4,
            obp_proxy=None,
            slg_proxy=None,
            strength_score=0.0,
            downgrade_score=0.85,
            warnings=unique_strings(warnings),
        )

    obp_proxy = clamp(0.285 + (strength - 0.5) * 0.10, 0.250, 0.380)
    slg_proxy = clamp(0.390 + (strength - 0.5) * 0.16, 0.320, 0.560)
    downgrade = clamp(1.0 - strength + (0.10 if games_played_before < 5 else 0.0), 0.0, 1.0)

    if games_played_before < 3:
        warnings.append("Projected lineup uses limited early-season team offense history.")
    else:
      warnings.append("Projected lineup uses team-level pre-game offense history only; no confirmed player lineup feed was available.")

    return LineupSideProxy(
        status="projected",
        players_count=9,
        top4_available=4,
        missing_key_batters=0,
        obp_proxy=obp_proxy,
        slg_proxy=slg_proxy,
        strength_score=round(strength, 4),
        downgrade_score=round(downgrade, 4),
        warnings=unique_strings(warnings),
    )


def lineup_quality_for_row(home_proxy: LineupSideProxy, away_proxy: LineupSideProxy) -> str:
    if home_proxy.status == "missing" and away_proxy.status == "missing":
        return "missing"
    if home_proxy.status == "projected" and away_proxy.status == "projected":
        if home_proxy.strength_score >= 0.6 and away_proxy.strength_score >= 0.6:
            return "high"
        if home_proxy.strength_score >= 0.45 and away_proxy.strength_score >= 0.45:
            return "medium"
        return "low"
    return "low"


def build_row(row: dict[str, str]) -> dict[str, Any]:
    home_proxy = build_side_proxy(row, "home")
    away_proxy = build_side_proxy(row, "away")
    quality = lineup_quality_for_row(home_proxy, away_proxy)
    warnings = unique_strings([
        *home_proxy.warnings,
        *away_proxy.warnings,
        "Lineup / player layer is research only and uses team-level proxies when confirmed player lineups are unavailable.",
        "No paid or authenticated lineup API is used.",
    ])

    return {
        "game_id": row.get("game_id") or "",
        "game_date": row.get("game_date") or "",
        "season": row.get("season") or "",
        "home_team": row.get("home_team") or "",
        "away_team": row.get("away_team") or "",
        "home_lineup_status": home_proxy.status,
        "away_lineup_status": away_proxy.status,
        "home_lineup_players_count": home_proxy.players_count,
        "away_lineup_players_count": away_proxy.players_count,
        "home_top4_batters_available": home_proxy.top4_available,
        "away_top4_batters_available": away_proxy.top4_available,
        "home_missing_key_batters_count": home_proxy.missing_key_batters,
        "away_missing_key_batters_count": away_proxy.missing_key_batters,
        "home_lineup_obp_proxy": csv_value(round_float(home_proxy.obp_proxy, 3)),
        "away_lineup_obp_proxy": csv_value(round_float(away_proxy.obp_proxy, 3)),
        "home_lineup_slg_proxy": csv_value(round_float(home_proxy.slg_proxy, 3)),
        "away_lineup_slg_proxy": csv_value(round_float(away_proxy.slg_proxy, 3)),
        "home_lineup_strength_score": csv_value(round_float(home_proxy.strength_score)),
        "away_lineup_strength_score": csv_value(round_float(away_proxy.strength_score)),
        "home_lineup_downgrade_score": csv_value(round_float(home_proxy.downgrade_score)),
        "away_lineup_downgrade_score": csv_value(round_float(away_proxy.downgrade_score)),
        "lineup_data_quality": quality,
        "lineup_warnings": " | ".join(warnings),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def merge_with_source(source_csv: Path, lineup_rows: list[dict[str, Any]], output_csv: Path) -> dict[str, Any]:
    if not source_csv.exists():
        return {
            "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
            "enhanced_rows_written": 0,
            "enhanced_output_csv": None,
            "enhanced_columns": [],
        }

    with source_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        base_rows = list(reader)
        base_columns = reader.fieldnames or []

    lineup_index = {
        (str(row.get("game_id") or ""), str(row.get("season") or "")): row
        for row in lineup_rows
    }

    merged_columns = list(base_columns)
    for column in LINEUP_COLUMNS:
        if column not in merged_columns:
            merged_columns.append(column)

    merged_rows: list[dict[str, Any]] = []
    for base_row in base_rows:
        key = (str(base_row.get("game_id") or ""), str(base_row.get("season") or ""))
        lineup_row = lineup_index.get(key, {})
        merged_row = dict(base_row)
        for column in LINEUP_COLUMNS:
            merged_row[column] = lineup_row.get(column, "")
        merged_rows.append(merged_row)

    write_csv(output_csv, merged_rows, merged_columns)
    return {
        "source_csv": str(source_csv.relative_to(ENGINE_ROOT)),
        "enhanced_rows_written": len(merged_rows),
        "enhanced_output_csv": str(output_csv.relative_to(ENGINE_ROOT)),
        "enhanced_columns": merged_columns,
    }


def quality_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"high": 0, "medium": 0, "low": 0, "missing": 0}
    for row in rows:
        quality = str(row.get("lineup_data_quality") or "missing")
        if quality not in summary:
            quality = "missing"
        summary[quality] += 1
    return summary


def main() -> None:
    ensure_dirs()
    print("ASTRODDS MLB Engine - build_lineup_player_features")
    print("Building safe research-only lineup/player proxies. No official picks, Strong Buys, ROI, CLV, Telegram, or real-money behavior will be created.")

    source_file = select_source_file()
    warnings: list[str] = []
    if source_file is None:
        warnings.append("No baseline moneyline feature CSV was found. Run build_features.py first.")
        report = {
            "status": "missing",
            "available": False,
            "games_read": 0,
            "games_with_confirmed_lineup_data": 0,
            "games_with_projected_or_proxy_lineup_data": 0,
            "games_missing_lineup_data": 0,
            "features_created": 0,
            "proxy_used": False,
            "proxy_method_used": "team-level pre-game offense proxy",
            "lineup_data_quality": "missing",
            "lineup_data_quality_summary": {"high": 0, "medium": 0, "low": 0, "missing": 0},
            "input_files_found": [],
            "source_csv": None,
            "merged_moneyline_output": None,
            "merged_pitcher_bullpen_weather_lineup_output": None,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with REPORT_OUTPUT.open("w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
        print(warnings[0])
        print(f"Report written: {REPORT_OUTPUT}")
        return

    rows = load_rows(source_file)
    lineup_rows = [build_row(row) for row in rows]
    standalone_columns = LINEUP_COLUMNS
    write_csv(STANDALONE_OUTPUT, lineup_rows, standalone_columns)

    confirmed_count = 0
    proxy_count = sum(1 for row in lineup_rows if row["home_lineup_status"] == "projected" or row["away_lineup_status"] == "projected")
    missing_count = sum(1 for row in lineup_rows if row["home_lineup_status"] == "missing" or row["away_lineup_status"] == "missing")
    available = proxy_count > 0
    status = "available" if available and missing_count == 0 else "partial" if available else "missing"
    quality_counts = quality_summary(lineup_rows)
    lineup_quality = "high" if quality_counts["high"] and not quality_counts["medium"] and not quality_counts["low"] and not quality_counts["missing"] else "medium" if quality_counts["high"] + quality_counts["medium"] > quality_counts["low"] + quality_counts["missing"] else "low" if available else "missing"
    warnings.append("No confirmed player lineup feed was available in the saved MLB data; this layer uses team-level offense proxies only.")
    warnings.append("Lineup / player features are research only and do not affect official picks yet.")
    warnings.append("Lineup counts are research diagnostics; a game can have one projected side and one missing side.")
    if missing_count:
        warnings.append("Some games still lack sufficient pre-game offense history for a safe lineup proxy.")

    merged_moneyline_summary = merge_with_source(PROCESSED_DIR / "mlb_moneyline_features.csv", lineup_rows, MERGED_MONEYLINE_OUTPUT)
    merged_rich_summary = merge_with_source(source_file, lineup_rows, MERGED_RICH_OUTPUT)

    report = {
        "status": status,
        "available": available,
        "games_read": len(rows),
        "games_with_confirmed_lineup_data": confirmed_count,
        "games_with_projected_or_proxy_lineup_data": proxy_count,
        "games_missing_lineup_data": missing_count,
        "features_created": len(lineup_rows),
        "proxy_used": available,
        "proxy_method_used": "team-level pre-game offense proxy from historical runs scored and run differential; no confirmed player lineup feed was available",
        "lineup_data_quality": lineup_quality,
        "lineup_data_quality_summary": quality_counts,
        "input_files_found": [str(source_file.relative_to(ENGINE_ROOT))],
        "source_csv": str(source_file.relative_to(ENGINE_ROOT)),
        "merged_moneyline_output": merged_moneyline_summary,
        "merged_pitcher_bullpen_weather_lineup_output": merged_rich_summary,
        "warnings": unique_strings([
            *warnings,
            "Lineup proxy values are research only and should not be interpreted as confirmed player lineups.",
        ]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with REPORT_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print("Lineup / player feature build completed.")
    print(f"- source CSV: {source_file.relative_to(ENGINE_ROOT)}")
    print(f"- games read: {len(rows)}")
    print(f"- projected/proxy lineup games: {proxy_count}")
    print(f"- missing lineup games: {missing_count}")
    print(f"- output CSV: {STANDALONE_OUTPUT}")
    print(f"- report JSON: {REPORT_OUTPUT}")
    if merged_moneyline_summary.get("enhanced_output_csv"):
        print(f"- merged moneyline CSV: {merged_moneyline_summary['enhanced_output_csv']}")
    if merged_rich_summary.get("enhanced_output_csv"):
        print(f"- merged richer CSV: {merged_rich_summary['enhanced_output_csv']}")
    for warning in report["warnings"]:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
