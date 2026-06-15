# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

SNAPSHOT = ROOT / ".astrodds" / "odds-snapshots" / "latest.json"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-mlb-gamepk-map-latest.json"
REPORT = BASE / "reports" / "109_mlb_gamepk_mapper_audit_report.txt"

ET = ZoneInfo("America/Toronto")

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
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def fetch_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def norm(name):
    return str(name or "").lower().replace(".", "").replace(" ", "").replace("-", "")

def aliases(name):
    return [norm(x) for x in TEAM_ALIASES.get(str(name or ""), [str(name or "")])]

def dt_local_date(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return None

def unique_games(snapshot):
    rows = (snapshot or {}).get("odds") or []
    seen = set()
    games = []

    for r in rows:
        key = "|".join([
            str(r.get("gameId") or ""),
            str(r.get("commenceTime") or ""),
            str(r.get("awayTeam") or ""),
            str(r.get("homeTeam") or ""),
        ])
        if key in seen:
            continue
        seen.add(key)
        games.append({
            "oddsGameId": r.get("gameId"),
            "commenceTime": r.get("commenceTime"),
            "dateLocal": dt_local_date(r.get("commenceTime")),
            "awayTeam": r.get("awayTeam"),
            "homeTeam": r.get("homeTeam"),
            "game": r.get("game"),
        })

    return games

def fetch_schedule(date_key):
    params = urllib.parse.urlencode({
        "sportId": 1,
        "date": date_key,
        "hydrate": "probablePitcher,team"
    })
    url = f"https://statsapi.mlb.com/api/v1/schedule?{params}"
    return fetch_json(url)

def match_game(snapshot_game, schedule):
    away_need = aliases(snapshot_game.get("awayTeam"))
    home_need = aliases(snapshot_game.get("homeTeam"))

    candidates = []
    for block in schedule.get("dates", []):
        for g in block.get("games", []):
            teams = g.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}

            away_name = ((away.get("team") or {}).get("name"))
            home_name = ((home.get("team") or {}).get("name"))

            away_ok = norm(away_name) in away_need or any(a in norm(away_name) for a in away_need)
            home_ok = norm(home_name) in home_need or any(h in norm(home_name) for h in home_need)

            if away_ok and home_ok:
                candidates.append(g)

    if len(candidates) == 1:
        return candidates[0], "matched"
    if len(candidates) > 1:
        return candidates[0], "multiple_matches_first_used"
    return None, "no_match"

def pitcher_name(side_obj):
    p = side_obj.get("probablePitcher") or {}
    return p.get("fullName") or p.get("name")

def main():
    generated_at = datetime.utcnow().isoformat() + "Z"
    snapshot = read_json(SNAPSHOT)
    games = unique_games(snapshot)

    schedules_by_date = {}
    mapped = []

    for sg in games:
        date_key = sg.get("dateLocal")
        if not date_key:
            mapped.append({**sg, "status": "no_date", "gamePk": None})
            continue

        if date_key not in schedules_by_date:
            try:
                schedules_by_date[date_key] = fetch_schedule(date_key)
            except Exception as e:
                schedules_by_date[date_key] = {"error": str(e), "dates": []}

        mlb_game, status = match_game(sg, schedules_by_date[date_key])

        if not mlb_game:
            mapped.append({
                **sg,
                "status": status,
                "gamePk": None,
                "mlbAwayTeam": None,
                "mlbHomeTeam": None,
                "gameStatus": None,
                "awayProbablePitcher": None,
                "homeProbablePitcher": None,
            })
            continue

        teams = mlb_game.get("teams") or {}
        away = teams.get("away") or {}
        home = teams.get("home") or {}

        mapped.append({
            **sg,
            "status": status,
            "gamePk": mlb_game.get("gamePk"),
            "mlbGameDate": mlb_game.get("gameDate"),
            "mlbAwayTeam": ((away.get("team") or {}).get("name")),
            "mlbHomeTeam": ((home.get("team") or {}).get("name")),
            "gameStatus": ((mlb_game.get("status") or {}).get("abstractGameState")),
            "detailedState": ((mlb_game.get("status") or {}).get("detailedState")),
            "awayProbablePitcher": pitcher_name(away),
            "homeProbablePitcher": pitcher_name(home),
        })

    counts = {
        "snapshotGames": len(games),
        "mapped": len([x for x in mapped if x.get("gamePk")]),
        "unmapped": len([x for x in mapped if not x.get("gamePk")]),
        "probablePitcherAwayFound": len([x for x in mapped if x.get("awayProbablePitcher")]),
        "probablePitcherHomeFound": len([x for x in mapped if x.get("homeProbablePitcher")]),
    }

    output = {
        "generatedAt": generated_at,
        "mode": "audit_only",
        "rules": {
            "source": "Odds snapshot + MLB StatsAPI schedule",
            "noTelegram": True,
            "noPublicSignal": True,
            "failSafe": "Unmapped games remain neutral. No picks are created or blocked by this audit.",
        },
        "counts": counts,
        "games": mapped,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 109 MLB GAMEPK MAPPER AUDIT",
        "=" * 60,
        f"Generated UTC: {generated_at}",
        "",
        "Rules:",
        "- Audit only.",
        "- No Telegram send.",
        "- No public signal change.",
        "- Maps The Odds API gameId to MLB gamePk using date/team matching.",
        "",
        "Counts:",
    ]

    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "Mapped games:"]

    if not mapped:
        lines.append("- none")
    else:
        for m in mapped[:20]:
            lines.append(
                f"- {m.get('game')} | oddsGameId={m.get('oddsGameId')} | gamePk={m.get('gamePk')} | "
                f"status={m.get('status')} | state={m.get('detailedState')} | "
                f"AwaySP={m.get('awayProbablePitcher') or '-'} | HomeSP={m.get('homeProbablePitcher') or '-'}"
            )

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: mapping audit only. Paper/manual only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
