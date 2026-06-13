from pathlib import Path
import csv
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mlb_schedule_results_2016_2026.csv"
REPORT = ROOT / "reports" / "confidence_gap_bucket_report.txt"

def pyth_pct(rf, ra):
    if rf <= 0 or ra <= 0:
        return 0.5
    exp = 1.83
    return (rf ** exp) / ((rf ** exp) + (ra ** exp))

def bucket_margin(margin):
    if margin < 0.01:
        return "0-1%"
    if margin < 0.02:
        return "1-2%"
    if margin < 0.03:
        return "2-3%"
    if margin < 0.05:
        return "3-5%"
    if margin < 0.08:
        return "5-8%"
    return "8%+"

with DATA.open("r", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

completed = []
for r in rows:
    if r["winner"] and r["home_win"] != "" and r["away_score"] != "" and r["home_score"] != "":
        r["season"] = int(r["season"])
        r["away_score"] = int(float(r["away_score"]))
        r["home_score"] = int(float(r["home_score"]))
        completed.append(r)

completed.sort(key=lambda x: (x["official_date"], str(x["game_id"])))

records = defaultdict(lambda: {"games": 0, "wins": 0, "rf": 0, "ra": 0})

for g in completed:
    season = g["season"]
    away = g["away_team"]
    home = g["home_team"]
    winner = g["winner"]
    away_score = g["away_score"]
    home_score = g["home_score"]

    records[(season, away)]["games"] += 1
    records[(season, away)]["rf"] += away_score
    records[(season, away)]["ra"] += home_score

    records[(season, home)]["games"] += 1
    records[(season, home)]["rf"] += home_score
    records[(season, home)]["ra"] += away_score

    if winner == away:
        records[(season, away)]["wins"] += 1
    elif winner == home:
        records[(season, home)]["wins"] += 1

history = defaultdict(list)
buckets = defaultdict(lambda: {"tested": 0, "correct": 0})

for g in completed:
    season = g["season"]
    away = g["away_team"]
    home = g["home_team"]
    winner = g["winner"]

    if season > 2016:
        prev = season - 1
        away_rec = records.get((prev, away))
        home_rec = records.get((prev, home))

        away_recent = history[away][-10:]
        home_recent = history[home][-10:]

        if away_rec and home_rec and len(away_recent) >= 5 and len(home_recent) >= 5:
            away_prev = away_rec["wins"] / away_rec["games"]
            home_prev = home_rec["wins"] / home_rec["games"]

            away_form = sum(away_recent) / len(away_recent)
            home_form = sum(home_recent) / len(home_recent)

            away_pyth = pyth_pct(away_rec["rf"], away_rec["ra"])
            home_pyth = pyth_pct(home_rec["rf"], home_rec["ra"])

            away_score = (away_prev * 0.60) + (away_form * 0.20) + (away_pyth * 0.20)
            home_score = (home_prev * 0.60) + (home_form * 0.20) + (home_pyth * 0.20)

            pick = home if home_score >= away_score else away
            margin = abs(home_score - away_score)
            bucket = bucket_margin(margin)

            buckets[bucket]["tested"] += 1
            if pick == winner:
                buckets[bucket]["correct"] += 1

    if winner == away:
        history[away].append(1)
        history[home].append(0)
    elif winner == home:
        history[away].append(0)
        history[home].append(1)

order = ["0-1%", "1-2%", "2-3%", "3-5%", "5-8%", "8%+"]

lines = []
lines.append("ASTRODDS CONFIDENCE GAP BUCKET REPORT")
lines.append("=" * 44)
lines.append("Formula: 60% previous record + 20% recent form + 20% Pythagorean")
lines.append("")
for b in order:
    tested = buckets[b]["tested"]
    correct = buckets[b]["correct"]
    acc = round((correct / tested) * 100, 2) if tested else 0
    lines.append(f"{b}: tested={tested} correct={correct} accuracy={acc}%")

REPORT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print("")
print(f"Saved: {REPORT}")
