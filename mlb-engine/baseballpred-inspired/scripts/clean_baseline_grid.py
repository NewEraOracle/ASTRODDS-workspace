from pathlib import Path
import csv
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mlb_schedule_results_2016_2026.csv"
REPORT = ROOT / "reports" / "clean_baseline_grid_report.txt"

def pyth_pct(rf, ra):
    if rf <= 0 or ra <= 0:
        return 0.5
    exp = 1.83
    return (rf ** exp) / ((rf ** exp) + (ra ** exp))

def load_completed():
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
    return completed

def build_prev_records(completed):
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

    return records

def test_formula(completed, records, prev_w, recent_w, pyth_w):
    history = defaultdict(list)
    tested = correct = skipped = 0

    for g in completed:
        season = g["season"]
        away = g["away_team"]
        home = g["home_team"]
        winner = g["winner"]

        if season > 2016:
            prev_season = season - 1
            away_rec = records.get((prev_season, away))
            home_rec = records.get((prev_season, home))

            away_recent = history[away][-10:]
            home_recent = history[home][-10:]

            if away_rec and home_rec and len(away_recent) >= 5 and len(home_recent) >= 5:
                away_prev = away_rec["wins"] / away_rec["games"]
                home_prev = home_rec["wins"] / home_rec["games"]

                away_form = sum(away_recent) / len(away_recent)
                home_form = sum(home_recent) / len(home_recent)

                away_pyth = pyth_pct(away_rec["rf"], away_rec["ra"])
                home_pyth = pyth_pct(home_rec["rf"], home_rec["ra"])

                away_score = away_prev * prev_w + away_form * recent_w + away_pyth * pyth_w
                home_score = home_prev * prev_w + home_form * recent_w + home_pyth * pyth_w

                pick = home if home_score >= away_score else away
                tested += 1
                if pick == winner:
                    correct += 1
            else:
                skipped += 1

        if winner == away:
            history[away].append(1)
            history[home].append(0)
        elif winner == home:
            history[away].append(0)
            history[home].append(1)

    acc = round((correct / tested) * 100, 2) if tested else 0
    return tested, correct, skipped, acc

def main():
    completed = load_completed()
    records = build_prev_records(completed)

    results = []

    for prev in range(0, 101, 10):
        for recent in range(0, 101 - prev, 10):
            pyth = 100 - prev - recent

            tested, correct, skipped, acc = test_formula(
                completed,
                records,
                prev / 100,
                recent / 100,
                pyth / 100,
            )

            results.append({
                "prev": prev,
                "recent": recent,
                "pyth": pyth,
                "tested": tested,
                "correct": correct,
                "skipped": skipped,
                "accuracy": acc,
            })

    results.sort(key=lambda x: x["accuracy"], reverse=True)

    lines = []
    lines.append("ASTRODDS CLEAN BASELINE GRID SEARCH")
    lines.append("=" * 40)
    lines.append(f"Completed games: {len(completed)}")
    lines.append("")
    lines.append("Top 10 formulas:")
    for r in results[:10]:
        lines.append(
            f"Prev {r['prev']}% | Recent {r['recent']}% | Pyth {r['pyth']}% "
            f"=> Accuracy {r['accuracy']}% | tested {r['tested']} | correct {r['correct']}"
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
