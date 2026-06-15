# -*- coding: utf-8 -*-
"""
ASTRODDS 111 - Bullpen Fatigue Context Audit

Audit-only sidecar module.
- Reads MLB gamePk map from .astrodds/ASTRODDS-mlb-gamepk-map-latest.json
- Uses MLB StatsAPI recent completed games
- Estimates bullpen usage by recent relief innings
- Produces neutral/warning/down-grade context
- Does NOT change picks, Telegram, or public board
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

GAMEPK_MAP = ROOT / ".astrodds" / "ASTRODDS-mlb-gamepk-map-latest.json"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-bullpen-fatigue-context-latest.json"
REPORT = BASE / "reports" / "111_bullpen_fatigue_context_audit_report.txt"

ET = ZoneInfo("America/Toronto")
DAYS_BACK = 5

TEAM_ALIASES = {
    "Athletics": ["Athletics", "Oakland Athletics"],
    "Arizona Diamondbacks": ["Arizona Diamondbacks"],
    "Atlanta Braves": ["Atlanta Braves"],
    "Baltimore Orioles": ["Baltimore Orioles"],
    "Boston Red Sox": ["Boston Red Sox"],
    "Chicago Cubs": ["Chicago Cubs"],
    "Chicago White Sox": ["Chicago White Sox"],
    "Cincinnati Reds": ["Cincinnati Reds"],
    "Cleveland Guardians": ["Cleveland Guardians"],
    "Colorado Rockies": ["Colorado Rockies"],
    "Detroit Tigers": ["Detroit Tigers"],
    "Houston Astros": ["Houston Astros"],
    "Kansas City Royals": ["Kansas City Royals"],
    "Los Angeles Angels": ["Los Angeles Angels"],
    "Los Angeles Dodgers": ["Los Angeles Dodgers"],
    "Miami Marlins": ["Miami Marlins"],
    "Milwaukee Brewers": ["Milwaukee Brewers"],
    "Minnesota Twins": ["Minnesota Twins"],
    "New York Mets": ["New York Mets"],
    "New York Yankees": ["New York Yankees"],
    "Philadelphia Phillies": ["Philadelphia Phillies"],
    "Pittsburgh Pirates": ["Pittsburgh Pirates"],
    "San Diego Padres": ["San Diego Padres"],
    "San Francisco Giants": ["San Francisco Giants"],
    "Seattle Mariners": ["Seattle Mariners"],
    "St. Louis Cardinals": ["St. Louis Cardinals"],
    "Tampa Bay Rays": ["Tampa Bay Rays"],
    "Texas Rangers": ["Texas Rangers"],
    "Toronto Blue Jays": ["Toronto Blue Jays"],
    "Washington Nationals": ["Washington Nationals"],
}

def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def fetch_json(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def norm(name):
    return str(name or "").lower().replace(".", "").replace(" ", "").replace("-", "")

def canonical_team(name):
    n = norm(name)
    for canon, vals in TEAM_ALIASES.items():
        if n in [norm(x) for x in vals]:
            return canon
    return str(name or "")

def parse_ip(value):
    """
    MLB innings pitched may be '1.0', '1.1', '1.2'.
    .1 = one out = 1/3 inning, .2 = two outs = 2/3 inning.
    """
    if value is None:
        return 0.0
    raw = str(value)
    if "." not in raw:
        try:
            return float(raw)
        except Exception:
            return 0.0

    whole, frac = raw.split(".", 1)
    try:
        base = int(whole)
    except Exception:
        base = 0

    if frac == "1":
        return base + (1 / 3)
    if frac == "2":
        return base + (2 / 3)

    try:
        return float(raw)
    except Exception:
        return float(base)

def local_date(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date()
    except Exception:
        return None

def fetch_recent_completed_games():
    today = datetime.now(ET).date()
    start = today - timedelta(days=DAYS_BACK)
    end = today - timedelta(days=1)

    params = urllib.parse.urlencode({
        "sportId": 1,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "hydrate": "team",
    })

    url = f"https://statsapi.mlb.com/api/v1/schedule?{params}"
    schedule = fetch_json(url)

    games = []
    for block in schedule.get("dates", []):
        for game in block.get("games", []):
            status = (game.get("status") or {}).get("abstractGameState")
            if str(status).lower() != "final":
                continue

            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}

            games.append({
                "gamePk": game.get("gamePk"),
                "gameDate": game.get("gameDate"),
                "awayTeam": canonical_team(((away.get("team") or {}).get("name"))),
                "homeTeam": canonical_team(((home.get("team") or {}).get("name"))),
            })

    return games

def pitcher_stats_from_boxscore(boxscore, side):
    team = (((boxscore.get("teams") or {}).get(side)) or {})
    pitcher_ids = team.get("pitchers") or []
    players = team.get("players") or {}

    rows = []
    for idx, pid in enumerate(pitcher_ids):
        player = players.get(f"ID{pid}") or {}
        person = player.get("person") or {}
        stats = ((player.get("stats") or {}).get("pitching") or {})
        ip = parse_ip(stats.get("inningsPitched"))
        rows.append({
            "name": person.get("fullName") or person.get("name") or str(pid),
            "inningsPitched": ip,
            "orderIndex": idx,
            "isStarterByOrder": idx == 0,
        })

    return rows

def build_team_bullpen_usage(recent_games):
    usage = {}

    for game in recent_games:
        game_pk = game.get("gamePk")
        if not game_pk:
            continue

        try:
            box = fetch_json(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore")
        except Exception:
            continue

        game_day = local_date(game.get("gameDate"))
        if not game_day:
            continue

        for side, team_name in [("away", game.get("awayTeam")), ("home", game.get("homeTeam"))]:
            team = canonical_team(team_name)
            usage.setdefault(team, [])

            pitchers = pitcher_stats_from_boxscore(box, side)
            if not pitchers:
                continue

            # Audit heuristic: first pitcher listed is treated as starter, rest = bullpen.
            relievers = pitchers[1:] if len(pitchers) > 1 else []
            relief_ip = sum(p["inningsPitched"] for p in relievers)
            reliever_count = len([p for p in relievers if p["inningsPitched"] > 0])

            usage[team].append({
                "gamePk": game_pk,
                "date": game_day.isoformat(),
                "reliefInnings": round(relief_ip, 2),
                "relieverCount": reliever_count,
            })

    return usage

def summarize_team_usage(team, usage):
    today = datetime.now(ET).date()
    rows = usage.get(canonical_team(team), [])

    def days_ago(row):
        try:
            d = datetime.fromisoformat(row["date"]).date()
            return (today - d).days
        except Exception:
            return 999

    last1 = [r for r in rows if days_ago(r) <= 1]
    last3 = [r for r in rows if days_ago(r) <= 3]
    last5 = [r for r in rows if days_ago(r) <= 5]

    ip1 = sum(r["reliefInnings"] for r in last1)
    ip3 = sum(r["reliefInnings"] for r in last3)
    ip5 = sum(r["reliefInnings"] for r in last5)
    games3 = len(last3)

    warnings = []
    impact = "NEUTRAL"
    confidence = "medium" if rows else "low"

    if not rows:
        warnings.append("no_recent_bullpen_data")
    if ip1 >= 4.0:
        warnings.append("heavy_bullpen_yesterday")
    if ip3 >= 10.0:
        warnings.append("high_bullpen_load_3d")
    if games3 >= 3 and ip3 >= 8.0:
        warnings.append("bullpen_used_multiple_recent_games")

    if ip1 >= 4.0 or ip3 >= 10.0:
        impact = "TIRED"
    elif ip3 <= 4.0 and games3 <= 2 and rows:
        impact = "RESTED"

    return {
        "team": canonical_team(team),
        "recentGamesTracked": len(rows),
        "reliefInnings1d": round(ip1, 2),
        "reliefInnings3d": round(ip3, 2),
        "reliefInnings5d": round(ip5, 2),
        "gamesTracked3d": games3,
        "impact": impact,
        "confidence": confidence,
        "warnings": warnings,
    }

def context_for_game(game, team_usage):
    away = canonical_team(game.get("awayTeam"))
    home = canonical_team(game.get("homeTeam"))

    away_summary = summarize_team_usage(away, team_usage)
    home_summary = summarize_team_usage(home, team_usage)

    warnings = []
    if away_summary["impact"] == "TIRED":
        warnings.append("away_bullpen_tired")
    if home_summary["impact"] == "TIRED":
        warnings.append("home_bullpen_tired")
    if away_summary["warnings"]:
        warnings.extend([f"away_{w}" for w in away_summary["warnings"]])
    if home_summary["warnings"]:
        warnings.extend([f"home_{w}" for w in home_summary["warnings"]])

    ou_impact = "NEUTRAL"
    adjustment_runs = 0.0

    tired_count = len([x for x in [away_summary["impact"], home_summary["impact"]] if x == "TIRED"])
    rested_count = len([x for x in [away_summary["impact"], home_summary["impact"]] if x == "RESTED"])

    if tired_count == 2:
        ou_impact = "OVER_BOOST"
        adjustment_runs = 0.35
    elif tired_count == 1:
        ou_impact = "OVER_LEAN"
        adjustment_runs = 0.20
    elif rested_count == 2:
        ou_impact = "UNDER_LEAN"
        adjustment_runs = -0.15

    return {
        "game": game.get("game"),
        "gamePk": game.get("gamePk"),
        "awayTeam": away,
        "homeTeam": home,
        "awayBullpen": away_summary,
        "homeBullpen": home_summary,
        "context": {
            "impact": ou_impact,
            "adjustmentRuns": adjustment_runs,
            "confidence": "medium",
            "warnings": warnings,
        },
    }

def main():
    generated_at = datetime.utcnow().isoformat() + "Z"

    mapping = read_json(GAMEPK_MAP)
    upcoming_games = mapping.get("games") or []
    recent_games = fetch_recent_completed_games()
    team_usage = build_team_bullpen_usage(recent_games)

    contexts = [context_for_game(g, team_usage) for g in upcoming_games]

    counts = {
        "upcomingGamesChecked": len(contexts),
        "recentCompletedGamesLoaded": len(recent_games),
        "teamsWithUsage": len(team_usage),
        "overBoost": len([c for c in contexts if c["context"]["impact"] == "OVER_BOOST"]),
        "overLean": len([c for c in contexts if c["context"]["impact"] == "OVER_LEAN"]),
        "underLean": len([c for c in contexts if c["context"]["impact"] == "UNDER_LEAN"]),
        "neutral": len([c for c in contexts if c["context"]["impact"] == "NEUTRAL"]),
        "warnings": len([c for c in contexts if c["context"]["warnings"]]),
    }

    output = {
        "generatedAt": generated_at,
        "mode": "audit_only",
        "rules": {
            "source": "MLB StatsAPI recent boxscores",
            "noTelegram": True,
            "noPublicSignal": True,
            "failSafe": "If bullpen data is unavailable, context stays neutral/warning only.",
            "note": "Starter/reliever split uses pitcher order heuristic, audit-only.",
        },
        "counts": counts,
        "contexts": contexts,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 111 BULLPEN FATIGUE CONTEXT AUDIT",
        "=" * 62,
        f"Generated UTC: {generated_at}",
        "",
        "Rules:",
        "- Audit only.",
        "- No Telegram send.",
        "- No public signal change.",
        "- Missing bullpen data = neutral/warning only.",
        "",
        "Counts:",
    ]

    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "Bullpen contexts:"]

    if not contexts:
        lines.append("- none")
    else:
        for c in contexts[:20]:
            ctx = c["context"]
            away = c["awayBullpen"]
            home = c["homeBullpen"]
            lines.append(
                f"- {c.get('game')} | "
                f"AwayBP={away['impact']} IP1={away['reliefInnings1d']} IP3={away['reliefInnings3d']} | "
                f"HomeBP={home['impact']} IP1={home['reliefInnings1d']} IP3={home['reliefInnings3d']} | "
                f"O/U Impact={ctx['impact']} | AdjRuns={ctx['adjustmentRuns']} | "
                f"Warnings={','.join(ctx['warnings']) or 'none'}"
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
