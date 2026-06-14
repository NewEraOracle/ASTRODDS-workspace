from pathlib import Path
import csv
import json
import urllib.request
from cache_utils import cached_get_json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

INPUT = ROOT / ".astrodds" / "VVS-clean-final-latest.json"
OUT_JSON = ROOT / ".astrodds" / "VVS-game-context-latest.json"
OUT_CSV = ROOT / ".astrodds" / "VVS-game-context-latest.csv"
REPORT = BASE / "reports" / "08_game_context_snapshot_report.txt"

REPORT.parent.mkdir(parents=True, exist_ok=True)

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def get_url_json(url, timeout=60):
    # Cached public data fetch. Reduces repeated API calls and timeout risk.
    namespace = "open_meteo" if "api.open-meteo.com" in url else "mlb_statsapi"

    ttl_seconds = 1800
    if namespace == "open_meteo":
        ttl_seconds = 3600

    data, source = cached_get_json(
        url,
        namespace=namespace,
        ttl_seconds=ttl_seconds,
        timeout=timeout
    )
    return data

def nested(obj, path, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def get_game_feed(game_id):
    game_pk = str(game_id).replace("mlb-", "").strip()
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    return get_url_json(url), game_pk

def extract_lineup_status(feed, side):
    team_box = nested(feed, ["liveData", "boxscore", "teams", side], {})
    players = team_box.get("players", {}) if isinstance(team_box, dict) else {}

    starters = []
    batting_orders = []

    for player_id, player in players.items():
        bo = player.get("battingOrder")
        if bo:
            batting_orders.append(str(bo))
            try:
                bo_num = int(str(bo))
                if bo_num in [100,200,300,400,500,600,700,800,900]:
                    starters.append(player.get("person", {}).get("fullName", player_id))
            except Exception:
                pass

    if len(starters) >= 9:
        return "confirmed", starters[:9]

    if batting_orders:
        return "partial", starters

    return "missing", []

def extract_probable_pitcher(feed, side):
    team = nested(feed, ["gameData", "probablePitchers", side], {})
    if isinstance(team, dict):
        return team.get("fullName")

    return None

def extract_venue(feed):
    venue = nested(feed, ["gameData", "venue"], {}) or {}
    venue_name = venue.get("name")
    coords = nested(venue, ["location", "defaultCoordinates"], {}) or {}

    lat = coords.get("latitude")
    lon = coords.get("longitude")

    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except Exception:
        lat = None
        lon = None

    return venue_name, lat, lon

def nearest_hour_weather(lat, lon, iso_date):
    if lat is None or lon is None or not iso_date:
        return None

    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).astimezone(timezone.utc)
        date = dt.strftime("%Y-%m-%d")
        target_hour = dt.strftime("%Y-%m-%dT%H:00")
    except Exception:
        return None

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation,wind_speed_10m,wind_direction_10m"
        f"&start_date={date}&end_date={date}&timezone=UTC"
    )

    try:
        data = get_url_json(url, timeout=30)
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return None

        if target_hour in times:
            idx = times.index(target_hour)
        else:
            idx = 0

        return {
            "weatherTime": times[idx],
            "temperatureC": hourly.get("temperature_2m", [None])[idx],
            "precipitationMm": hourly.get("precipitation", [None])[idx],
            "windSpeedKmh": hourly.get("wind_speed_10m", [None])[idx],
            "windDirectionDeg": hourly.get("wind_direction_10m", [None])[idx],
        }
    except Exception as e:
        return {"weatherError": str(e)}

def main():
    picks = read_json(INPUT)
    output = []
    errors = []

    for pick in picks:
        row = dict(pick)
        game_id = row.get("gameId")

        try:
            feed, game_pk = get_game_feed(game_id)
        except Exception as e:
            errors.append(f"{game_id}: {e}")
            row["contextStatus"] = "feed_failed"
            row["contextError"] = str(e)
            output.append(row)
            continue

        status = nested(feed, ["gameData", "status", "detailedState"], "")
        abstract = nested(feed, ["gameData", "status", "abstractGameState"], "")

        away_pitcher = extract_probable_pitcher(feed, "away")
        home_pitcher = extract_probable_pitcher(feed, "home")

        away_lineup_status, away_starters = extract_lineup_status(feed, "away")
        home_lineup_status, home_starters = extract_lineup_status(feed, "home")

        venue_name, lat, lon = extract_venue(feed)
        weather = nearest_hour_weather(lat, lon, row.get("date"))

        row["gamePk"] = game_pk
        row["mlbDetailedStatus"] = status
        row["mlbAbstractStatus"] = abstract
        row["venue"] = venue_name
        row["venueLatitude"] = lat
        row["venueLongitude"] = lon

        row["awayProbablePitcher"] = away_pitcher
        row["homeProbablePitcher"] = home_pitcher
        row["probablePitcherStatus"] = "available" if away_pitcher and home_pitcher else "missing_or_partial"

        row["awayLineupStatus"] = away_lineup_status
        row["homeLineupStatus"] = home_lineup_status
        row["awayLineupCount"] = len(away_starters)
        row["homeLineupCount"] = len(home_starters)

        if weather:
            for k, v in weather.items():
                row[k] = v
            row["weatherStatus"] = "available" if "weatherError" not in weather else "error"
        else:
            row["weatherStatus"] = "missing"

        missing = []
        if not away_pitcher or not home_pitcher:
            missing.append("probable_pitcher")
        if away_lineup_status != "confirmed" or home_lineup_status != "confirmed":
            missing.append("confirmed_lineup")
        if row["weatherStatus"] != "available":
            missing.append("weather")
        missing.append("bullpen_fatigue_not_built")
        missing.append("advanced_pitcher_stats_not_built")

        row["missingFeatureFlags"] = "|".join(missing)
        row["contextStatus"] = "ok"
        output.append(row)

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    fieldnames = sorted({key for row in output for key in row.keys()})

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    lines = []
    lines.append("ASTRODDS 08 GAME CONTEXT SNAPSHOT REPORT")
    lines.append("=" * 44)
    lines.append(f"Input picks: {len(picks)}")
    lines.append(f"Output rows: {len(output)}")
    lines.append("")
    lines.append("Context rows:")

    for row in output:
        lines.append(
            f"- {row.get('game')} | Pick: {row.get('pick')} | "
            f"Pitchers: {row.get('awayProbablePitcher')} vs {row.get('homeProbablePitcher')} | "
            f"Lineups: away={row.get('awayLineupStatus')} home={row.get('homeLineupStatus')} | "
            f"Weather: {row.get('weatherStatus')} | Missing: {row.get('missingFeatureFlags')}"
        )

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

