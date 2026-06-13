from pathlib import Path
import csv
import json
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mlb_schedule_results_2016_2026.csv"
OUT = ROOT / "data" / "processed" / "astrodss_master_feature_dataset_v1.csv"
REPORT = ROOT / "reports" / "13_master_feature_dataset_report.txt"
MANIFEST = ROOT / "reports" / "13_master_feature_dataset_manifest.json"

def fnum(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(str(x).replace(",", "."))
    except Exception:
        return default

def inum(x, default=None):
    try:
        if x is None or x == "":
            return default
        return int(float(str(x).replace(",", ".")))
    except Exception:
        return default

def pyth_pct(rf, ra):
    rf = fnum(rf, 0)
    ra = fnum(ra, 0)
    if rf <= 0 or ra <= 0:
        return None
    exp = 1.83
    return (rf ** exp) / ((rf ** exp) + (ra ** exp))

def pct(x):
    if x is None:
        return ""
    return round(float(x), 6)

def gap_bucket(gap):
    if gap is None:
        return "missing"
    if gap < 0.01:
        return "0-1%"
    if gap < 0.02:
        return "1-2%"
    if gap < 0.03:
        return "2-3%"
    if gap < 0.05:
        return "3-5%"
    if gap < 0.08:
        return "5-8%"
    return "8%+"

def parse_date(row):
    raw = row.get("official_date") or row.get("date") or row.get("game_date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10])
    except Exception:
        return None

def load_completed():
    with DATA.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    completed = []
    for r in rows:
        away_score = inum(r.get("away_score"))
        home_score = inum(r.get("home_score"))
        winner = r.get("winner", "")
        season = inum(r.get("season"))

        if season and winner and away_score is not None and home_score is not None:
            r["season"] = season
            r["away_score"] = away_score
            r["home_score"] = home_score
            r["_date"] = parse_date(r)
            completed.append(r)

    completed.sort(key=lambda x: (x.get("official_date", ""), str(x.get("game_id", ""))))
    return completed

def build_season_records(rows):
    rec = defaultdict(lambda: {
        "games": 0,
        "wins": 0,
        "rf": 0,
        "ra": 0,
        "home_games": 0,
        "home_wins": 0,
        "away_games": 0,
        "away_wins": 0,
    })

    for g in rows:
        season = g["season"]
        away = g.get("away_team")
        home = g.get("home_team")
        winner = g.get("winner")
        away_score = g["away_score"]
        home_score = g["home_score"]

        ak = (season, away)
        hk = (season, home)

        rec[ak]["games"] += 1
        rec[ak]["away_games"] += 1
        rec[ak]["rf"] += away_score
        rec[ak]["ra"] += home_score

        rec[hk]["games"] += 1
        rec[hk]["home_games"] += 1
        rec[hk]["rf"] += home_score
        rec[hk]["ra"] += away_score

        if winner == away:
            rec[ak]["wins"] += 1
            rec[ak]["away_wins"] += 1

        if winner == home:
            rec[hk]["wins"] += 1
            rec[hk]["home_wins"] += 1

    return rec

def avg(values):
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)

def recent_win_pct(history, team, n=10):
    vals = history[team][-n:]
    if len(vals) < 5:
        return None
    return avg([x["win"] for x in vals])

def recent_run_diff(history, team, n=10):
    vals = history[team][-n:]
    if len(vals) < 5:
        return None
    return avg([x["rf"] - x["ra"] for x in vals])

def recent_runs_for(history, team, n=10):
    vals = history[team][-n:]
    if len(vals) < 5:
        return None
    return avg([x["rf"] for x in vals])

def recent_runs_against(history, team, n=10):
    vals = history[team][-n:]
    if len(vals) < 5:
        return None
    return avg([x["ra"] for x in vals])

def days_rest(last_date, team, current_date):
    if team not in last_date or not current_date:
        return None
    return (current_date - last_date[team]).days

def pitcher_name(row, side):
    keys = [
        f"{side}_probable_pitcher",
        f"{side}ProbablePitcher",
        f"{side}_starter",
        f"{side}_starting_pitcher",
    ]
    for k in keys:
        if k in row and row.get(k):
            return row.get(k)
    return ""

def pitcher_prior_stats(pitcher_history, pitcher):
    if not pitcher:
        return {
            "starts": 0,
            "win_pct": None,
            "avg_ip": None,
        }

    h = pitcher_history.get(pitcher)
    if not h or h["starts"] == 0:
        return {
            "starts": 0,
            "win_pct": None,
            "avg_ip": None,
        }

    return {
        "starts": h["starts"],
        "win_pct": h["wins"] / h["starts"],
        "avg_ip": h["ip"] / h["starts"] if h["starts"] else None,
    }

def update_pitcher_history(pitcher_history, pitcher, team_won):
    if not pitcher:
        return
    if pitcher not in pitcher_history:
        pitcher_history[pitcher] = {
            "starts": 0,
            "wins": 0,
            "ip": 0.0,
        }
    pitcher_history[pitcher]["starts"] += 1
    if team_won:
        pitcher_history[pitcher]["wins"] += 1

def main():
    rows = load_completed()
    season_records = build_season_records(rows)

    team_history = defaultdict(list)
    pitcher_history = {}
    last_game_date = {}

    output = []

    tested = 0
    correct = 0
    bucket_stats = defaultdict(lambda: {"tested": 0, "correct": 0})

    for g in rows:
        season = g["season"]
        prev_season = season - 1

        away = g.get("away_team")
        home = g.get("home_team")
        winner = g.get("winner")
        game_date = g.get("_date")

        away_score = g["away_score"]
        home_score = g["home_score"]

        away_prev = season_records.get((prev_season, away))
        home_prev = season_records.get((prev_season, home))

        away_prev_win = away_prev["wins"] / away_prev["games"] if away_prev and away_prev["games"] else None
        home_prev_win = home_prev["wins"] / home_prev["games"] if home_prev and home_prev["games"] else None

        away_prev_pyth = pyth_pct(away_prev["rf"], away_prev["ra"]) if away_prev else None
        home_prev_pyth = pyth_pct(home_prev["rf"], home_prev["ra"]) if home_prev else None

        away_prev_run_diff = ((away_prev["rf"] - away_prev["ra"]) / away_prev["games"]) if away_prev and away_prev["games"] else None
        home_prev_run_diff = ((home_prev["rf"] - home_prev["ra"]) / home_prev["games"]) if home_prev and home_prev["games"] else None

        away_prev_away_win = away_prev["away_wins"] / away_prev["away_games"] if away_prev and away_prev["away_games"] else None
        home_prev_home_win = home_prev["home_wins"] / home_prev["home_games"] if home_prev and home_prev["home_games"] else None

        away_recent = recent_win_pct(team_history, away)
        home_recent = recent_win_pct(team_history, home)

        away_recent_rd = recent_run_diff(team_history, away)
        home_recent_rd = recent_run_diff(team_history, home)

        away_recent_rf = recent_runs_for(team_history, away)
        home_recent_rf = recent_runs_for(team_history, home)

        away_recent_ra = recent_runs_against(team_history, away)
        home_recent_ra = recent_runs_against(team_history, home)

        away_rest = days_rest(last_game_date, away, game_date)
        home_rest = days_rest(last_game_date, home, game_date)

        away_pitcher = pitcher_name(g, "away")
        home_pitcher = pitcher_name(g, "home")

        away_pitch = pitcher_prior_stats(pitcher_history, away_pitcher)
        home_pitch = pitcher_prior_stats(pitcher_history, home_pitcher)

        model_ready = (
            away_prev_win is not None
            and home_prev_win is not None
            and away_prev_pyth is not None
            and home_prev_pyth is not None
            and away_recent is not None
            and home_recent is not None
        )

        away_model_score = None
        home_model_score = None
        model_pick = ""
        model_correct = ""

        if model_ready:
            away_model_score = (away_prev_win * 0.60) + (away_recent * 0.20) + (away_prev_pyth * 0.20)
            home_model_score = (home_prev_win * 0.60) + (home_recent * 0.20) + (home_prev_pyth * 0.20)

            model_pick = home if home_model_score >= away_model_score else away
            model_correct = 1 if model_pick == winner else 0

            tested += 1
            correct += model_correct

            gap = abs(home_model_score - away_model_score)
            b = gap_bucket(gap)
            bucket_stats[b]["tested"] += 1
            bucket_stats[b]["correct"] += model_correct
        else:
            gap = None
            b = "missing"

        out = {
            "game_id": g.get("game_id"),
            "season": season,
            "official_date": g.get("official_date"),
            "away_team": away,
            "home_team": home,
            "away_score": away_score,
            "home_score": home_score,
            "winner": winner,
            "home_win": 1 if winner == home else 0,

            "away_prev_win_pct": pct(away_prev_win),
            "home_prev_win_pct": pct(home_prev_win),
            "away_prev_pyth": pct(away_prev_pyth),
            "home_prev_pyth": pct(home_prev_pyth),
            "away_prev_run_diff_pg": pct(away_prev_run_diff),
            "home_prev_run_diff_pg": pct(home_prev_run_diff),
            "away_prev_away_win_pct": pct(away_prev_away_win),
            "home_prev_home_win_pct": pct(home_prev_home_win),

            "away_recent10_win_pct": pct(away_recent),
            "home_recent10_win_pct": pct(home_recent),
            "away_recent10_run_diff_pg": pct(away_recent_rd),
            "home_recent10_run_diff_pg": pct(home_recent_rd),
            "away_recent10_runs_for": pct(away_recent_rf),
            "home_recent10_runs_for": pct(home_recent_rf),
            "away_recent10_runs_against": pct(away_recent_ra),
            "home_recent10_runs_against": pct(home_recent_ra),

            "away_rest_days": away_rest if away_rest is not None else "",
            "home_rest_days": home_rest if home_rest is not None else "",

            "away_probable_pitcher": away_pitcher,
            "home_probable_pitcher": home_pitcher,
            "away_pitcher_prior_starts": away_pitch["starts"],
            "home_pitcher_prior_starts": home_pitch["starts"],
            "away_pitcher_prior_team_win_pct": pct(away_pitch["win_pct"]),
            "home_pitcher_prior_team_win_pct": pct(home_pitch["win_pct"]),
            "away_pitcher_prior_avg_ip": pct(away_pitch["avg_ip"]),
            "home_pitcher_prior_avg_ip": pct(home_pitch["avg_ip"]),

            "model_ready": 1 if model_ready else 0,
            "away_model_score": pct(away_model_score),
            "home_model_score": pct(home_model_score),
            "model_score_gap": pct(gap),
            "model_score_gap_bucket": b,
            "model_pick": model_pick,
            "model_correct": model_correct,
        }

        output.append(out)

        away_won = winner == away
        home_won = winner == home

        team_history[away].append({"win": 1 if away_won else 0, "rf": away_score, "ra": home_score})
        team_history[home].append({"win": 1 if home_won else 0, "rf": home_score, "ra": away_score})

        if game_date:
            last_game_date[away] = game_date
            last_game_date[home] = game_date

        update_pitcher_history(pitcher_history, away_pitcher, away_won)
        update_pitcher_history(pitcher_history, home_pitcher, home_won)

    fieldnames = list(output[0].keys())
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    accuracy = round((correct / tested) * 100, 2) if tested else 0

    manifest = {
        "rows": len(output),
        "testedRows": tested,
        "correct": correct,
        "modelAccuracy": accuracy,
        "features": fieldnames,
        "output": str(OUT),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 13 MASTER FEATURE DATASET")
    lines.append("=" * 40)
    lines.append(f"Input completed games: {len(rows)}")
    lines.append(f"Output feature rows: {len(output)}")
    lines.append(f"Model-ready rows: {tested}")
    lines.append(f"Model correct: {correct}")
    lines.append(f"Model V1 accuracy on master dataset: {accuracy}%")
    lines.append("")
    lines.append("Score gap buckets:")

    for bucket in ["0-1%", "1-2%", "2-3%", "3-5%", "5-8%", "8%+"]:
        s = bucket_stats[bucket]
        if s["tested"]:
            acc = round((s["correct"] / s["tested"]) * 100, 2)
        else:
            acc = 0
        lines.append(f"- {bucket}: tested={s['tested']} correct={s['correct']} accuracy={acc}%")

    lines.append("")
    lines.append("Features included:")
    lines.append("- previous season win pct")
    lines.append("- previous season Pythagorean")
    lines.append("- previous season run differential")
    lines.append("- previous season home/away splits")
    lines.append("- rolling recent 10-game form")
    lines.append("- rolling recent 10-game run differential")
    lines.append("- rest days")
    lines.append("- pitcher prior starts / prior team win rate")
    lines.append("- Model V1 score and correctness")
    lines.append("")
    lines.append("Important:")
    lines.append("This dataset uses only prior information before each game. No future leakage from same-game result.")
    lines.append("")
    lines.append(f"CSV: {OUT}")
    lines.append(f"Manifest: {MANIFEST}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
