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

REPORT = BASE / "reports" / "102_over_under_probability_backtest_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-over-under-probability-backtest-latest.json"

ET = ZoneInfo("America/Toronto")
MAX_RUNS = 16

# Safe audit defaults. No Telegram. No public signal.
DAYS_BACK = 21
EDGE_THRESHOLDS = [0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.05]
BET_WIN_UNITS = 1.0
BET_LOSS_UNITS = -1.10

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

def team_key(name):
    raw = str(name or "").strip()
    return TEAM_ALIASES.get(raw, raw)

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

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

def fetch_completed_games(days_back=DAYS_BACK):
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
    data = fetch_json(url)

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

            away_score = away.get("score")
            home_score = home.get("score")

            if not away_team or not home_team or away_score is None or home_score is None:
                continue

            try:
                away_score = int(away_score)
                home_score = int(home_score)
            except Exception:
                continue

            games.append({
                "date": game.get("gameDate"),
                "awayTeam": away_team,
                "homeTeam": home_team,
                "awayRuns": away_score,
                "homeRuns": home_score,
                "totalRuns": away_score + home_score,
            })

    return games

def build_profiles_from_prior_games(games, cutoff_index, lookback_games=12):
    prior = games[:cutoff_index]
    by_team = {}

    for g in prior:
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

    if not prior:
        return {}, 4.5, 9.0

    league_avg_team_runs = sum(g["totalRuns"] for g in prior) / max(1, len(prior)) / 2

    profiles = {}
    for team, rows in by_team.items():
        recent = rows[-lookback_games:]
        if not recent:
            continue

        profiles[team] = {
            "games": len(recent),
            "runsForAvg": sum(x["runsFor"] for x in recent) / len(recent),
            "runsAgainstAvg": sum(x["runsAgainst"] for x in recent) / len(recent),
        }

    return profiles, league_avg_team_runs, league_avg_team_runs * 2

def project_team_runs(away_team, home_team, profiles, league_avg_team_runs):
    away = profiles.get(team_key(away_team))
    home = profiles.get(team_key(home_team))

    if not away or not home:
        return None, None

    away_raw = (away["runsForAvg"] + home["runsAgainstAvg"]) / 2
    home_raw = (home["runsForAvg"] + away["runsAgainstAvg"]) / 2

    sample_games = min(away["games"], home["games"])
    weight = min(0.72, max(0.40, sample_games / 16))

    away_proj = (away_raw * weight) + (league_avg_team_runs * (1 - weight))
    home_proj = (home_raw * weight) + (league_avg_team_runs * (1 - weight))

    return away_proj, home_proj

def estimate_market_line(game, league_avg_total):
    """
    Backtest-safe proxy because historical sportsbook closing totals are not yet stored in the repo.
    This does NOT prove real betting edge. It tests model behavior until we store historical odds.
    """
    total = game["totalRuns"]
    baseline = round(league_avg_total * 2) / 2
    # Keep realistic MLB range.
    return max(6.5, min(12.5, baseline))

def result_for_pick(side, line, total_runs):
    if total_runs > line:
        actual = "Over"
    elif total_runs < line:
        actual = "Under"
    else:
        actual = "Push"

    if actual == "Push":
        return "PUSH"
    return "WIN" if actual.lower() == side.lower() else "LOSS"

def run_backtest():
    games = fetch_completed_games(DAYS_BACK)
    games = sorted(games, key=lambda x: str(x.get("date") or ""))

    decisions = []

    for idx, game in enumerate(games):
        profiles, league_avg_team_runs, league_avg_total = build_profiles_from_prior_games(games, idx)

        away_proj, home_proj = project_team_runs(
            game["awayTeam"],
            game["homeTeam"],
            profiles,
            league_avg_team_runs,
        )

        if away_proj is None or home_proj is None:
            continue

        line = estimate_market_line(game, league_avg_total)
        away_dist = poisson_dist(away_proj)
        home_dist = poisson_dist(home_proj)
        probs = ou_probs(away_dist, home_dist, line)

        # Backtest proxy: compare to 50/50 no-vig baseline.
        over_edge = probs["probOverNoPush"] - 0.50
        under_edge = probs["probUnderNoPush"] - 0.50

        if over_edge >= under_edge:
            side = "Over"
            model_prob = probs["probOverNoPush"]
            edge = over_edge
        else:
            side = "Under"
            model_prob = probs["probUnderNoPush"]
            edge = under_edge

        result = result_for_pick(side, line, game["totalRuns"])

        decisions.append({
            "date": game["date"],
            "game": f"{game['awayTeam']} @ {game['homeTeam']}",
            "pick": f"{side} {line:g}",
            "line": line,
            "totalRuns": game["totalRuns"],
            "awayRuns": game["awayRuns"],
            "homeRuns": game["homeRuns"],
            "awayProjectedRuns": round(away_proj, 2),
            "homeProjectedRuns": round(home_proj, 2),
            "projectedTotalRuns": round(away_proj + home_proj, 2),
            "modelProbability": round(model_prob, 4),
            "probabilityEdge": round(edge, 4),
            "probOver": round(probs["probOver"], 4),
            "probUnder": round(probs["probUnder"], 4),
            "probPush": round(probs["probPush"], 4),
            "result": result,
        })

    threshold_reports = []

    for threshold in EDGE_THRESHOLDS:
        rows = [d for d in decisions if d["probabilityEdge"] >= threshold]
        wins = sum(1 for r in rows if r["result"] == "WIN")
        losses = sum(1 for r in rows if r["result"] == "LOSS")
        pushes = sum(1 for r in rows if r["result"] == "PUSH")
        graded = wins + losses
        units = (wins * BET_WIN_UNITS) + (losses * BET_LOSS_UNITS)
        roi = units / graded if graded else 0.0

        threshold_reports.append({
            "threshold": threshold,
            "bets": len(rows),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "graded": graded,
            "winRate": round(wins / graded, 4) if graded else None,
            "units": round(units, 2),
            "roiPerBet": round(roi, 4),
        })

    return games, decisions, threshold_reports

def main():
    games, decisions, threshold_reports = run_backtest()

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "audit_only",
        "model": "ASTRODDS_OU_PROBABILITY_BACKTEST_V1",
        "importantNote": "This uses a proxy market line because historical sportsbook totals are not yet stored. It validates model behavior, not proven real betting edge.",
        "rules": {
            "market": "Over/Under full-game totals only",
            "method": "prior games -> team run projections -> Poisson O/U probabilities -> threshold evaluation",
            "noTelegram": True,
            "noPublicSignal": True,
        },
        "counts": {
            "completedGamesLoaded": len(games),
            "decisionsBuilt": len(decisions),
        },
        "thresholdReports": threshold_reports,
        "sampleDecisions": decisions[:20],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 102 OVER/UNDER PROBABILITY BACKTEST",
        "=" * 64,
        f"Generated UTC: {output['generatedAt']}",
        "",
        "IMPORTANT:",
        "- Audit only.",
        "- No Telegram send.",
        "- Uses proxy market line because historical sportsbook totals are not stored yet.",
        "- This checks model behavior, not final real betting profitability.",
        "",
        "Counts:",
        f"- completedGamesLoaded: {len(games)}",
        f"- decisionsBuilt: {len(decisions)}",
        "",
        "Threshold results:",
    ]

    for r in threshold_reports:
        wr = "-" if r["winRate"] is None else f"{r['winRate']:.2%}"
        lines.append(
            f"- edge >= {r['threshold']:.2%} | bets={r['bets']} | "
            f"W-L-P={r['wins']}-{r['losses']}-{r['pushes']} | "
            f"winRate={wr} | units={r['units']} | roiPerBet={r['roiPerBet']}"
        )

    lines += [
        "",
        "Sample decisions:",
    ]

    if not decisions:
        lines.append("- none")
    else:
        for d in decisions[:20]:
            lines.append(
                f"- {d['game']} | Pick={d['pick']} | Total={d['totalRuns']} | "
                f"Projected={d['projectedTotalRuns']} | Edge={d['probabilityEdge']:.2%} | Result={d['result']}"
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
