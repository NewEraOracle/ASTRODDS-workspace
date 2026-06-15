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

REPORT = BASE / "reports" / "100_over_under_probability_edge_model_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-over-under-probability-edge-model-latest.json"

ODDS_URL = "http://localhost:3000/api/astrodds/odds/status?sportKey=baseball_mlb&fetch=true"
ET = ZoneInfo("America/Toronto")
MAX_RUNS = 16

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
    raw = str(name or "").strip()
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

def poisson_dist(lam, max_runs=MAX_RUNS):
    lam = max(0.2, min(12.0, float(lam)))
    probs = []
    for k in range(max_runs):
        probs.append(math.exp(-lam) * (lam ** k) / math.factorial(k))
    tail = max(0.0, 1.0 - sum(probs))
    probs.append(tail)
    return probs

def ou_probs(away_dist, home_dist, line):
    val = float(line)
    over = 0.0
    under = 0.0
    push = 0.0

    for a, pa in enumerate(away_dist):
        for h, ph in enumerate(home_dist):
            total = a + h
            p = pa * ph
            if total > val:
                over += p
            elif total < val:
                under += p
            else:
                push += p

    no_push = max(0.000001, over + under)

    return {
        "probOver": over,
        "probUnder": under,
        "probPush": push,
        "probOverNoPush": over / no_push,
        "probUnderNoPush": under / no_push,
    }

def fetch_recent_mlb_games(days_back=35):
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

            away_team = team_key((away.get("team") or {}).get("name"))
            home_team = team_key((home.get("team") or {}).get("name"))
            away_runs = away.get("score")
            home_runs = home.get("score")

            if not away_team or not home_team or away_runs is None or home_runs is None:
                continue

            try:
                away_runs = int(away_runs)
                home_runs = int(home_runs)
            except Exception:
                continue

            games.append({
                "date": game.get("gameDate"),
                "awayTeam": away_team,
                "homeTeam": home_team,
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

    league_avg_team_runs = sum(g["totalRuns"] for g in games) / max(1, len(games)) / 2
    league_avg_total = league_avg_team_runs * 2

    profiles = {}
    for team, rows in by_team.items():
        recent = rows[-12:]
        if not recent:
            continue

        profiles[team] = {
            "games": len(recent),
            "runsForAvg": sum(x["runsFor"] for x in recent) / len(recent),
            "runsAgainstAvg": sum(x["runsAgainst"] for x in recent) / len(recent),
            "gameTotalAvg": sum(x["totalRuns"] for x in recent) / len(recent),
        }

    return profiles, league_avg_team_runs, league_avg_total

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

def project_team_runs(away_team, home_team, profiles, league_avg_team_runs):
    away = profiles.get(team_key(away_team))
    home = profiles.get(team_key(home_team))

    if not away or not home:
        return None, None, ["missing_team_recent_profile"]

    away_raw = (away["runsForAvg"] + home["runsAgainstAvg"]) / 2
    home_raw = (home["runsForAvg"] + away["runsAgainstAvg"]) / 2

    sample_games = min(away["games"], home["games"])
    weight = min(0.72, max(0.40, sample_games / 16))

    away_proj = (away_raw * weight) + (league_avg_team_runs * (1 - weight))
    home_proj = (home_raw * weight) + (league_avg_team_runs * (1 - weight))

    reasons = [
        f"away_rf={away['runsForAvg']:.2f}",
        f"away_ra={away['runsAgainstAvg']:.2f}",
        f"home_rf={home['runsForAvg']:.2f}",
        f"home_ra={home['runsAgainstAvg']:.2f}",
        f"sample_games={sample_games}",
        f"weight={weight:.2f}",
    ]

    return away_proj, home_proj, reasons

def classify_candidate(over, under, profiles, league_avg_team_runs):
    line = fnum(over.get("line"))
    if line is None:
        return None

    if line < 5.5 or line > 13.5:
        return None

    if not price_ok(over) or not price_ok(under):
        return None

    away_team = team_key(over.get("awayTeam"))
    home_team = team_key(over.get("homeTeam"))

    away_proj, home_proj, reasons = project_team_runs(away_team, home_team, profiles, league_avg_team_runs)
    if away_proj is None or home_proj is None:
        return None

    away_dist = poisson_dist(away_proj)
    home_dist = poisson_dist(home_proj)
    probs = ou_probs(away_dist, home_dist, line)

    over_market = fnum(over.get("impliedProbability"))
    under_market = fnum(under.get("impliedProbability"))

    if over_market is None or under_market is None:
        return None

    over_edge = probs["probOverNoPush"] - over_market
    under_edge = probs["probUnderNoPush"] - under_market

    if over_edge >= under_edge:
        side = "Over"
        model_prob = probs["probOverNoPush"]
        market_prob = over_market
        edge = over_edge
        row = over
    else:
        side = "Under"
        model_prob = probs["probUnderNoPush"]
        market_prob = under_market
        edge = under_edge
        row = under

    projected_total = away_proj + home_proj
    edge_runs = projected_total - line

    if edge < 0.05:
        return None

    category = "O/U_WATCH"
    stake = "No stake"

    if edge >= 0.12 and abs(edge_runs) >= 0.75:
        category = "O/U_PICK"
        stake = "3% max / paper"
    elif edge >= 0.08 and abs(edge_runs) >= 0.50:
        category = "O/U_LEAN"
        stake = "1-2% max / paper"

    return {
        "category": category,
        "stake": stake,
        "date": row.get("commenceTime"),
        "game": row.get("game"),
        "awayTeam": away_team,
        "homeTeam": home_team,
        "pick": f"{side} {line:g}",
        "line": line,
        "awayProjectedRuns": round(away_proj, 2),
        "homeProjectedRuns": round(home_proj, 2),
        "projectedTotalRuns": round(projected_total, 2),
        "edgeRuns": round(edge_runs, 2),
        "modelProbability": round(model_prob, 4),
        "marketProbability": round(market_prob, 4),
        "probabilityEdge": round(edge, 4),
        "probOver": round(probs["probOver"], 4),
        "probUnder": round(probs["probUnder"], 4),
        "probPush": round(probs["probPush"], 4),
        "priceAmerican": row.get("priceAmerican"),
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
    recent_games = fetch_recent_mlb_games(days_back=35)
    profiles, league_avg_team_runs, league_avg_total = build_team_profiles(recent_games)

    candidates = []
    for over, under in pairs:
        c = classify_candidate(over, under, profiles, league_avg_team_runs)
        if c:
            candidates.append(c)

    candidates.sort(key=lambda x: x.get("probabilityEdge") or 0, reverse=True)

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "audit_only",
        "model": "ASTRODDS_OU_PROBABILITY_EDGE_V2_BASEBALLPRED_STYLE",
        "rules": {
            "market": "Over/Under full-game totals only",
            "source": "sportsbook totals only",
            "method": "team expected runs -> Poisson distributions -> Over/Under/Push probabilities",
            "publicSend": False,
            "ouPick": "probabilityEdge >= 12% and abs(edgeRuns) >= 0.75",
            "ouLean": "probabilityEdge >= 8% and abs(edgeRuns) >= 0.50",
            "excluded": ["runline/spread", "props", "futures"],
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
        "leagueAvgTeamRuns": round(league_avg_team_runs, 2),
        "leagueAvgTotalRuns": round(league_avg_total, 2),
        "candidates": candidates[:12],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 100 OVER/UNDER PROBABILITY EDGE MODEL",
        "=" * 64,
        f"Generated UTC: {output['generatedAt']}",
        "",
        "Rules:",
        "- BaseballPred-style O/U probability edge.",
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
        f"- leagueAvgTeamRuns: {output['leagueAvgTeamRuns']}",
        f"- leagueAvgTotalRuns: {output['leagueAvgTotalRuns']}",
        "",
        "O/U probability candidates:",
    ]

    if not candidates:
        lines.append("- none")
    else:
        for c in candidates[:12]:
            lines.append(
                f"- {c['category']} | {c['game']} | Pick={c['pick']} | "
                f"ModelProb={c['modelProbability']:.2%} | MarketProb={c['marketProbability']:.2%} | "
                f"ProbEdge={c['probabilityEdge']:.2%} | Projected={c['projectedTotalRuns']} | "
                f"Line={c['line']} | EdgeRuns={c['edgeRuns']} | Price={american_label(c.get('priceAmerican'))} | "
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
