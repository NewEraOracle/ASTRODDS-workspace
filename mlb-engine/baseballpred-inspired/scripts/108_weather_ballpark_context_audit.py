# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse
import math

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "108_weather_ballpark_context_audit_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-weather-ballpark-context-latest.json"

ODDS_SNAPSHOT_LATEST = ROOT / ".astrodds" / "odds-snapshots" / "latest.json"
ET = ZoneInfo("America/Toronto")

# Static free local registry.
# This is intentionally local so the bot does not depend on paid APIs.
BALLPARKS = {
    "Arizona Diamondbacks": {"park": "Chase Field", "lat": 33.4455, "lon": -112.0667, "roof": "retractable", "runFactor": "neutral"},
    "Atlanta Braves": {"park": "Truist Park", "lat": 33.8908, "lon": -84.4678, "roof": "open", "runFactor": "neutral"},
    "Baltimore Orioles": {"park": "Oriole Park at Camden Yards", "lat": 39.2840, "lon": -76.6217, "roof": "open", "runFactor": "neutral"},
    "Boston Red Sox": {"park": "Fenway Park", "lat": 42.3467, "lon": -71.0972, "roof": "open", "runFactor": "hitter"},
    "Chicago Cubs": {"park": "Wrigley Field", "lat": 41.9484, "lon": -87.6553, "roof": "open", "runFactor": "wind_sensitive"},
    "Chicago White Sox": {"park": "Rate Field", "lat": 41.8300, "lon": -87.6339, "roof": "open", "runFactor": "neutral"},
    "Cincinnati Reds": {"park": "Great American Ball Park", "lat": 39.0975, "lon": -84.5066, "roof": "open", "runFactor": "hitter"},
    "Cleveland Guardians": {"park": "Progressive Field", "lat": 41.4962, "lon": -81.6852, "roof": "open", "runFactor": "neutral"},
    "Colorado Rockies": {"park": "Coors Field", "lat": 39.7559, "lon": -104.9942, "roof": "open", "runFactor": "hitter"},
    "Detroit Tigers": {"park": "Comerica Park", "lat": 42.3390, "lon": -83.0485, "roof": "open", "runFactor": "neutral"},
    "Houston Astros": {"park": "Daikin Park", "lat": 29.7573, "lon": -95.3555, "roof": "retractable", "runFactor": "neutral"},
    "Kansas City Royals": {"park": "Kauffman Stadium", "lat": 39.0517, "lon": -94.4803, "roof": "open", "runFactor": "neutral"},
    "Los Angeles Angels": {"park": "Angel Stadium", "lat": 33.8003, "lon": -117.8827, "roof": "open", "runFactor": "neutral"},
    "Los Angeles Dodgers": {"park": "Dodger Stadium", "lat": 34.0739, "lon": -118.2400, "roof": "open", "runFactor": "pitcher"},
    "Miami Marlins": {"park": "loanDepot park", "lat": 25.7781, "lon": -80.2197, "roof": "retractable", "runFactor": "neutral"},
    "Milwaukee Brewers": {"park": "American Family Field", "lat": 43.0280, "lon": -87.9712, "roof": "retractable", "runFactor": "neutral"},
    "Minnesota Twins": {"park": "Target Field", "lat": 44.9817, "lon": -93.2776, "roof": "open", "runFactor": "neutral"},
    "New York Mets": {"park": "Citi Field", "lat": 40.7571, "lon": -73.8458, "roof": "open", "runFactor": "pitcher"},
    "New York Yankees": {"park": "Yankee Stadium", "lat": 40.8296, "lon": -73.9262, "roof": "open", "runFactor": "hitter"},
    "Athletics": {"park": "Sutter Health Park", "lat": 38.5803, "lon": -121.5130, "roof": "open", "runFactor": "unknown"},
    "Philadelphia Phillies": {"park": "Citizens Bank Park", "lat": 39.9058, "lon": -75.1665, "roof": "open", "runFactor": "hitter"},
    "Pittsburgh Pirates": {"park": "PNC Park", "lat": 40.4469, "lon": -80.0057, "roof": "open", "runFactor": "neutral"},
    "San Diego Padres": {"park": "Petco Park", "lat": 32.7073, "lon": -117.1566, "roof": "open", "runFactor": "pitcher"},
    "San Francisco Giants": {"park": "Oracle Park", "lat": 37.7786, "lon": -122.3893, "roof": "open", "runFactor": "pitcher"},
    "Seattle Mariners": {"park": "T-Mobile Park", "lat": 47.5914, "lon": -122.3325, "roof": "retractable", "runFactor": "pitcher"},
    "St. Louis Cardinals": {"park": "Busch Stadium", "lat": 38.6226, "lon": -90.1928, "roof": "open", "runFactor": "neutral"},
    "Tampa Bay Rays": {"park": "George M. Steinbrenner Field", "lat": 27.9802, "lon": -82.5066, "roof": "open", "runFactor": "unknown"},
    "Texas Rangers": {"park": "Globe Life Field", "lat": 32.7473, "lon": -97.0842, "roof": "retractable", "runFactor": "neutral"},
    "Toronto Blue Jays": {"park": "Rogers Centre", "lat": 43.6414, "lon": -79.3894, "roof": "retractable", "runFactor": "neutral"},
    "Washington Nationals": {"park": "Nationals Park", "lat": 38.8730, "lon": -77.0074, "roof": "open", "runFactor": "neutral"},
}

def read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def fetch_json(url, timeout=25):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def dt_et(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET)
    except Exception:
        return None

def fnum(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).replace(",", "."))
    except Exception:
        return None

def closest_hour_index(hourly_times, game_dt):
    best_i = None
    best_diff = None
    for i, t in enumerate(hourly_times or []):
        try:
            hdt = datetime.fromisoformat(str(t))
            hdt = hdt.replace(tzinfo=ET)
            diff = abs((hdt - game_dt).total_seconds())
            if best_diff is None or diff < best_diff:
                best_i = i
                best_diff = diff
        except Exception:
            continue
    return best_i

def weather_url(lat, lon, game_dt):
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/Toronto",
        "start_date": game_dt.date().isoformat(),
        "end_date": game_dt.date().isoformat(),
    })
    return f"https://api.open-meteo.com/v1/forecast?{params}"

def circular_wind_bucket(direction):
    deg = fnum(direction)
    if deg is None:
        return "UNKNOWN"

    # IMPORTANT:
    # We do not know exact stadium orientation yet.
    # This is only a rough weather audit, not a direct pick engine.
    if 135 <= deg <= 225:
        return "ROUGH_OUT_TO_CENTER_OR_LEFT"
    if deg <= 45 or deg >= 315:
        return "ROUGH_IN_FROM_CENTER_OR_RIGHT"
    return "CROSSWIND_OR_SIDE"

def classify_weather_context(row, park, weather):
    warnings = []
    impact = "NEUTRAL"
    adjustment_runs = 0.0
    confidence = "low"

    if not park:
        return {
            "status": "unavailable",
            "impact": "NEUTRAL",
            "adjustmentRuns": 0,
            "confidence": "low",
            "warnings": ["missing_ballpark_registry"],
        }

    if not weather:
        return {
            "status": "unavailable",
            "impact": "NEUTRAL",
            "adjustmentRuns": 0,
            "confidence": "low",
            "warnings": ["weather_api_unavailable"],
        }

    roof = park.get("roof")
    if roof in ["dome", "retractable"]:
        warnings.append("roof_or_retractable_weather_may_be_neutralized")

    temp = fnum(weather.get("temperatureF"))
    wind = fnum(weather.get("windMph"))
    gust = fnum(weather.get("gustMph"))
    precip_prob = fnum(weather.get("precipitationProbability"))
    precip = fnum(weather.get("precipitationIn"))
    wind_bucket = circular_wind_bucket(weather.get("windDirectionDeg"))

    if temp is not None:
        if temp >= 82:
            adjustment_runs += 0.15
            warnings.append("hot_weather_over_support")
        elif temp <= 50:
            adjustment_runs -= 0.15
            warnings.append("cold_weather_under_support")

    if wind is not None:
        if wind >= 15:
            warnings.append("strong_wind")
            confidence = "medium"
        elif wind >= 9:
            warnings.append("moderate_wind")
            confidence = "medium"

        if wind >= 9 and wind_bucket == "ROUGH_OUT_TO_CENTER_OR_LEFT":
            adjustment_runs += 0.20
            warnings.append("rough_wind_out_over_support")
        elif wind >= 9 and wind_bucket == "ROUGH_IN_FROM_CENTER_OR_RIGHT":
            adjustment_runs -= 0.20
            warnings.append("rough_wind_in_under_support")

    if gust is not None and gust >= 22:
        warnings.append("high_wind_gusts")

    if precip_prob is not None and precip_prob >= 45:
        warnings.append("rain_delay_risk")
        confidence = "low"

    if precip is not None and precip > 0.03:
        warnings.append("active_precipitation_risk")
        confidence = "low"

    if adjustment_runs >= 0.25:
        impact = "OVER_BOOST"
    elif adjustment_runs <= -0.25:
        impact = "UNDER_BOOST"
    elif warnings:
        impact = "WEATHER_WARNING"

    if roof in ["dome", "retractable"]:
        # Keep roof games conservative. Do not boost unless roof status is known later.
        adjustment_runs = 0.0
        impact = "NEUTRAL"
        confidence = "low"

    return {
        "status": "available",
        "impact": impact,
        "adjustmentRuns": round(adjustment_runs, 2),
        "confidence": confidence,
        "warnings": warnings,
    }

def unique_games_from_snapshot(snapshot):
    odds = (snapshot or {}).get("odds") or []
    seen = set()
    games = []

    for r in odds:
        key = "|".join([
            str(r.get("gameId") or ""),
            str(r.get("commenceTime") or ""),
            str(r.get("awayTeam") or ""),
            str(r.get("homeTeam") or ""),
        ])
        if key in seen:
            continue
        seen.add(key)
        games.append(r)

    return games

def main():
    generated_at = datetime.utcnow().isoformat() + "Z"
    snapshot = read_json(ODDS_SNAPSHOT_LATEST)

    games = unique_games_from_snapshot(snapshot)
    contexts = []

    for g in games:
        home = g.get("homeTeam")
        away = g.get("awayTeam")
        game_dt = dt_et(g.get("commenceTime"))
        park = BALLPARKS.get(str(home or ""))

        weather_obs = None
        weather_status = "not_requested"

        if park and game_dt:
            try:
                url = weather_url(park["lat"], park["lon"], game_dt)
                data = fetch_json(url)
                hourly = data.get("hourly") or {}
                idx = closest_hour_index(hourly.get("time"), game_dt)

                if idx is not None:
                    weather_obs = {
                        "temperatureF": (hourly.get("temperature_2m") or [None])[idx],
                        "humidityPct": (hourly.get("relative_humidity_2m") or [None])[idx],
                        "precipitationProbability": (hourly.get("precipitation_probability") or [None])[idx],
                        "precipitationIn": (hourly.get("precipitation") or [None])[idx],
                        "windMph": (hourly.get("wind_speed_10m") or [None])[idx],
                        "windDirectionDeg": (hourly.get("wind_direction_10m") or [None])[idx],
                        "gustMph": (hourly.get("wind_gusts_10m") or [None])[idx],
                    }
                    weather_status = "available"
                else:
                    weather_status = "missing_hour"
            except Exception as e:
                weather_status = "error"
                weather_obs = None

        context = classify_weather_context(g, park, weather_obs)

        contexts.append({
            "gameId": g.get("gameId"),
            "date": g.get("commenceTime"),
            "awayTeam": away,
            "homeTeam": home,
            "game": g.get("game"),
            "ballpark": park,
            "weatherStatus": weather_status,
            "weather": weather_obs,
            "context": context,
        })

    counts = {
        "gamesChecked": len(games),
        "weatherAvailable": len([x for x in contexts if x["weatherStatus"] == "available"]),
        "weatherUnavailable": len([x for x in contexts if x["weatherStatus"] != "available"]),
        "overBoost": len([x for x in contexts if x["context"]["impact"] == "OVER_BOOST"]),
        "underBoost": len([x for x in contexts if x["context"]["impact"] == "UNDER_BOOST"]),
        "warnings": len([x for x in contexts if x["context"]["warnings"]]),
    }

    output = {
        "generatedAt": generated_at,
        "mode": "audit_only",
        "rules": {
            "source": "Open-Meteo + local ballpark registry",
            "noTelegram": True,
            "noPublicSignal": True,
            "failSafe": "If weather is unavailable, impact is neutral and adjustmentRuns is 0.",
            "note": "Wind direction is rough until stadium orientation is added.",
        },
        "counts": counts,
        "contexts": contexts,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 108 WEATHER + BALLPARK CONTEXT AUDIT",
        "=" * 64,
        f"Generated UTC: {generated_at}",
        "",
        "Rules:",
        "- Audit only.",
        "- No Telegram send.",
        "- No public signal change.",
        "- If weather fails, impact stays NEUTRAL.",
        "- Weather helps O/U later, but does not create picks by itself.",
        "",
        "Counts:",
    ]

    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "Weather contexts:"]

    if not contexts:
        lines.append("- none")
    else:
        for c in contexts[:20]:
            ctx = c["context"]
            w = c.get("weather") or {}
            park = c.get("ballpark") or {}
            lines.append(
                f"- {c.get('game')} | Park={park.get('park', '-')} | "
                f"Temp={w.get('temperatureF', '-')}F | Wind={w.get('windMph', '-')} mph | "
                f"Gust={w.get('gustMph', '-')} mph | RainProb={w.get('precipitationProbability', '-')}% | "
                f"Impact={ctx.get('impact')} | AdjRuns={ctx.get('adjustmentRuns')} | "
                f"Confidence={ctx.get('confidence')} | Warnings={','.join(ctx.get('warnings') or []) or 'none'}"
            )

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: context audit only. Paper/manual only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
