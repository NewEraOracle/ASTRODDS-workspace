# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse
import math

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "98_over_under_expected_total_model_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-over-under-expected-total-model-latest.json"

ODDS_URL = "http://localhost:3000/api/astrodds/odds/status?sportKey=baseball_mlb&fetch=true"
ET = ZoneInfo("America/Toronto")

TEAM_ALIASES = {
    "Athletics": "Athletics",
    "Oakland Athletics": "Athletics",
    "A's": "Athletics",

    "Arizona Diamondbacks": "Arizona Diamondbacks",
    "Atlanta Braves": "Atlanta Braves",
    "Baltimore Orioles": "Baltimore Orioles",
    "Boston Red Sox": "Boston Red Sox",
    "Chicago Cubs": "Chicago Cubs",
    "Chicago White Sox": "Chicago White Sox",
    "Cincinnati Reds": "Cincinnati Reds",
    "Cleveland Guardians": "Cleveland Guardians",
    "Colorado Rockies": "Colorado Rockies",
    "Detroit Tigers": "Detroit Tigers",
    "Houston Astros": "Houston Astros",
    "Kansas City Royals": "Kansas City Royals",
    "Los Angeles Angels": "Los Angeles Angels",
    "Los Angeles Dodgers": "Los Angeles Dodgers",
    "Miami Marlins": "Miami Marlins",
    "Milwaukee Brewers": "Milwaukee Brewers",
    "Minnesota Twins": "Minnesota Twins",
    "New York Mets": "New York Mets",
    "New York Yankees": "New York Yankees",
    "Philadelphia Phillies": "Philadelphia Phillies",
    "Pittsburgh Pirates": "Pittsburgh Pirates",
    "San Diego Padres": "San Diego Padres",
    "San Francisco Giants": "San Francisco Giants",
    "Seattle Mariners": "Seattle Mariners",
    "St. Louis Cardinals": "St. Louis Cardinals",
    "Tampa Bay Rays": "Tampa Bay Rays",
    "Texas Rangers": "Texas Rangers",
    "Toronto Blue Jays": "Toronto Blue Jays",
    "Washington Nationals": "Washington Nationals",
}

def fetch_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def team_key(name):
    if not name:
        return ""
    raw = str(name).strip()
    return TEAM_ALIASES.get(raw, raw)

def et_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET)
    except Exception:
        return None

def is_today(value):
    dt = et_dt(value)
    if not dt:
        return False
    return dt.date().isoformat() == datetime.now(ET).date().isoformat()

def is_pregame(value):
    dt = et_dt(value)
    if not dt:
        return False
    return dt > datetime.now(ET)

def american_label(value):
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except Exception:
        return "-"

def price_ok(row):
    american = fnum(row.get("priceAmerican"))
    implied = fnum(row.get("impliedProbability"))

    if implied is None:
        return False
    if american is not None and (american < -190 or american > 180):
        return False

    return 0.35 <= implied <= 0.67

def fetch_recent_mlb_games(days_back=21):
    today = datetime.now(ET).date()
    start = today - timedelta(days=days_back)
    end = today - timedelta(days=1)

    params = urllib.parse.urlencode({
        "sportId": 1,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "hydrate": "team",
    })

    url = f"https://statsapi.mlb.com/api/v1/schedule?{params}"
    data = fetch_json(url, timeout=60)

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            status = (game.get("status") or {}).get("abstractGameState")
            if str(status).lower() != "final":
                continue

            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}

            away_team = ((away.get("team") or {}).get("name"))
            home_team = ((home.get("team") or {}).get("name"))

            away_runs = away.get("score")
            home_runs = home.get("score")

            if away_team is None or home_team is None:
                continue
            if away_runs is None or home_runs is None:
                continue

            try:
                away_runs = int(away_runs)
                home_runs = int(home_runs)
            except Exception:
                continue

            games.append({
                "date": game.get("gameDate"),
                "awayTeam": team_key(away_team),
                "homeTeam": team_key(home_team),
                "awayRuns": away_runs,
                "homeRuns": home_runs,
                "totalRuns": away_runs + home_runs,
            })

    return games

def build_team_profiles(games):
    by_team = {}

    for g in games:
        away = team_key(g["awayTeam"])
        home = team_key(g["homeTeam"])

        by_team.setdefault(away, [])
        by_team.setdefault(home, [])

        by_team[away].append({
            "runsFor": g["awayRuns"],
            "runsAgainst": g["homeRuns"],
            "totalRuns": g["totalRuns"],
        })

        by_team[home].append({
            "runsFor": g["homeRuns"],
            "runsAgainst": g["awayRuns"],
            "totalRuns": g["totalRuns"],
        })

    league_avg_total = sum(g["totalRuns"] for g in games) / max(1, len(games))

    profiles = {}
    for team, rows in by_team.items():
        recent = rows[-10:]
        if not recent:
            continue

        profiles[team] = {
            "games": len(recent),
            "runsForAvg": sum(x["runsFor"] for x in recent) / len(recent),
            "runsAgainstAvg": sum(x["runsAgainst"] for x in recent) / len(recent),
            "gameTotalAvg": sum(x["totalRuns"] for x in recent) / len(recent),
        }

    return profiles, league_avg_total

def pair_total_rows(rows):
    groups = {}

    for r in rows:
        key = "|".join([
            str(r.get("gameId") or ""),
            str(r.get("commenceTime") or ""),
            team_key(r.get("awayTeam")),
            team_key(r.get("homeTeam")),
            str(r.get("line") or ""),
        ])
        groups.setdefault(key, []).append(r)

    pairs = []
    for _, items in groups.items():
        over = next((x for x in items if str(x.get("side")).lower() == "over"), None)
        under = next((x for x in items if str(x.get("side")).lower() == "under"), None)
        if over and under:
            pairs.append((over, under))

    return pairs

def project_total_runs(away_team, home_team, profiles, league_avg_total):
    away = profiles.get(team_key(away_team))
    home = profiles.get(team_key(home_team))

    if not away or not home:
        return None, ["missing_team_recent_profile"]

    raw_away_runs = (away["runsForAvg"] + home["runsAgainstAvg"]) / 2
    raw_home_runs = (home["runsForAvg"] + away["runsAgainstAvg"]) / 2
    raw_total = raw_away_runs + raw_home_runs

    sample_games = min(away["games"], home["games"])
    confidence_weight = min(0.70, max(0.35, sample_games / 14))

    projected = (raw_total * confidence_weight) + (league_avg_total * (1 - confidence_weight))

    reasons = [
        f"away_rf={away['runsForAvg']:.2f}",
        f"away_ra={away['runsAgainstAvg']:.2f}",
        f"home_rf={home['runsForAvg']:.2f}",
        f"home_ra={home['runsAgainstAvg']:.2f}",
        f"league_avg_total={league_avg_total:.2f}",
        f"sample_games={sample_games}",
    ]

    return projected, reasons

def classify_ou_candidate(over, under, profiles, league_avg_total):
    line = fnum(over.get("line"))
    if line is None:
        return None

    if line < 5.5 or line > 13.5:
        return None

    away_team = team_key(over.get("awayTeam"))
    home_team = team_key(over.get("homeTeam"))

    projected, reasons = project_total_runs(away_team, home_team, profiles, league_avg_total)
    if projected is None:
        return None

    edge_runs = projected - line

    if abs(edge_runs) < 0.60:
        return None

    pick_side = "Over" if edge_runs > 0 else "Under"
    row = over if pick_side == "Over" else under

    if not price_ok(row):
        return None

    abs_edge = abs(edge_runs)

    if abs_edge >= 1.25:
        category = "O/U_PICK"
        stake = "3% max / paper"
    elif abs_edge >= 0.75:
        category = "O/U_LEAN"
        stake = "1-2% max / paper"
    else:
        category = "O/U_WATCH"
        stake = "No stake"

    return {
        "category": category,
        "stake": stake,
        "date": row.get("commenceTime"),
        "game": row.get("game"),
        "awayTeam": away_team,
        "homeTeam": home_team,
        "pick": f"{pick_side} {line:g}",
        "line": line,
        "projectedTotalRuns": round(projected, 2),
        "edgeRuns": round(edge_runs, 2),
        "priceAmerican": row.get("priceAmerican"),
        "impliedProbability": fnum(row.get("impliedProbability")),
        "overAmerican": over.get("priceAmerican"),
        "underAmerican": under.get("priceAmerican"),
        "reason": " | ".join(reasons),
    }

def main():
    odds_payload = fetch_json(ODDS_URL, timeout=60)
    odds = odds_payload.get("odds") or []

    total_rows = [
        r for r in odds
        if str(r.get("marketType") or "").lower() == "total"
        and str(r.get("side") or "").lower() in ["over", "under"]
        and r.get("line") is not None
    ]

    today_pregame_total_rows = [
        r for r in total_rows
        if is_today(r.get("commenceTime"))
        and is_pregame(r.get("commenceTime"))
    ]

    pairs = pair_total_rows(today_pregame_total_rows)

    recent_games = fetch_recent_mlb_games(days_back=21)
    profiles, league_avg_total = build_team_profiles(recent_games)

    candidates = []
    for over, under in pairs:
        c = classify_ou_candidate(over, under, profiles, league_avg_total)
        if c:
            candidates.append(c)

    candidates.sort(key=lambda x: abs(x.get("edgeRuns") or 0), reverse=True)

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "audit_only",
        "model": "ASTRODDS_OU_EXPECTED_TOTAL_V1",
        "rules": {
            "market": "Over/Under full-game totals only",
            "source": "sportsbook totals only",
            "excluded": ["runline/spread", "props", "futures", "tomorrow public picks"],
            "publicSend": False,
            "ouPick": "abs(edgeRuns) >= 1.25 and price ok",
            "ouLean": "abs(edgeRuns) >= 0.75 and price ok",
        },
        "counts": {
            "oddsRows": len(odds),
            "totalRows": len(total_rows),
            "todayPregameTotalRows": len(today_pregame_total_rows),
            "pairedTodayPregameTotals": len(pairs),
            "recentCompletedMlbGames": len(recent_games),
            "teamProfiles": len(profiles),
            "ouPicks": len([x for x in candidates if x["category"] == "O/U_PICK"]),
            "ouLeans": len([x for x in candidates if x["category"] == "O/U_LEAN"]),
            "ouWatch": len([x for x in candidates if x["category"] == "O/U_WATCH"]),
        },
        "leagueAvgTotalRuns": round(league_avg_total, 2),
        "candidates": candidates[:12],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 98 OVER/UNDER EXPECTED TOTAL MODEL",
        "=" * 60,
        f"Generated UTC: {output['generatedAt']}",
        "",
        "Rules:",
        "- Full-game Over/Under totals only.",
        "- No runline/spread.",
        "- No props.",
        "- Same-day pre-game only.",
        "- Audit only. No Telegram send.",
        "",
        "Counts:",
    ]

    for k, v in output["counts"].items():
        lines.append(f"- {k}: {v}")

    lines += [
        f"- leagueAvgTotalRuns: {output['leagueAvgTotalRuns']}",
        "",
        "O/U candidates:",
    ]

    if not candidates:
        lines.append("- none")
    else:
        for c in candidates[:12]:
            lines.append(
                f"- {c['category']} | {c['game']} | Pick={c['pick']} | "
                f"Line={c['line']} | Projected={c['projectedTotalRuns']} | "
                f"EdgeRuns={c['edgeRuns']} | Price={american_label(c.get('priceAmerican'))} | "
                f"Stake={c['stake']} | Reason={c['reason']}"
            )

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: Paper/manual only. No real-money automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
