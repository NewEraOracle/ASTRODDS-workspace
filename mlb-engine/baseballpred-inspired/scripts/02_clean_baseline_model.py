from pathlib import Path
import csv
import json
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mlb_schedule_results_2016_2026.csv"
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"

REPORTS.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

GRID_CSV = REPORTS / "clean_baseline_grid_results.csv"
REPORT_TXT = REPORTS / "02_clean_baseline_report.txt"
MODEL_JSON = MODELS / "ASTRODDS_MLB_MONEYLINE_MODEL_V1.json"
MODEL_JSON_COPY = REPORTS / "ASTRODDS_MLB_MONEYLINE_MODEL_V1.json"

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

def build_records(completed):
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

def test_formula(completed, records, prev_w, recent_w, pyth_w, collect_buckets=False):
    history = defaultdict(list)
    tested = 0
    correct = 0
    skipped = 0
    buckets = defaultdict(lambda: {"tested": 0, "correct": 0})

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
                margin = abs(home_score - away_score)

                tested += 1
                if pick == winner:
                    correct += 1

                if collect_buckets:
                    b = bucket_margin(margin)
                    buckets[b]["tested"] += 1
                    if pick == winner:
                        buckets[b]["correct"] += 1
            else:
                skipped += 1

        if winner == away:
            history[away].append(1)
            history[home].append(0)
        elif winner == home:
            history[away].append(0)
            history[home].append(1)

    acc = round((correct / tested) * 100, 2) if tested else 0
    return {
        "tested": tested,
        "correct": correct,
        "skipped": skipped,
        "accuracy": acc,
        "buckets": buckets,
    }

def main():
    completed = load_completed()
    records = build_records(completed)

    grid = []

    for prev in range(0, 101, 10):
        for recent in range(0, 101 - prev, 10):
            pyth = 100 - prev - recent

            result = test_formula(
                completed,
                records,
                prev / 100,
                recent / 100,
                pyth / 100,
            )

            grid.append({
                "previous_record_weight": prev,
                "recent_form_weight": recent,
                "pythagorean_weight": pyth,
                "tested": result["tested"],
                "correct": result["correct"],
                "skipped": result["skipped"],
                "accuracy": result["accuracy"],
            })

    grid.sort(key=lambda x: x["accuracy"], reverse=True)
    best = grid[0]

    bucket_result = test_formula(
        completed,
        records,
        best["previous_record_weight"] / 100,
        best["recent_form_weight"] / 100,
        best["pythagorean_weight"] / 100,
        collect_buckets=True,
    )

    with GRID_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)

    bucket_order = ["0-1%", "1-2%", "2-3%", "3-5%", "5-8%", "8%+"]
    bucket_summary = {}

    for b in bucket_order:
        tested = bucket_result["buckets"][b]["tested"]
        correct = bucket_result["buckets"][b]["correct"]
        acc = round((correct / tested) * 100, 2) if tested else 0
        bucket_summary[b] = {
            "tested": tested,
            "correct": correct,
            "accuracy": acc,
        }

    model_config = {
        "modelName": "ASTRODDS_MLB_MONEYLINE_MODEL_V1",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "dataset": {
            "source": str(DATA),
            "completedGames": len(completed),
            "seasons": "2016-2026 regular season completed games",
        },
        "formula": {
            "previousSeasonRecordWeight": best["previous_record_weight"] / 100,
            "recent10GameFormWeight": best["recent_form_weight"] / 100,
            "previousSeasonPythagoreanWeight": best["pythagorean_weight"] / 100,
        },
        "historicalBacktest": {
            "overallAccuracy": best["accuracy"],
            "testedGames": best["tested"],
            "correct": best["correct"],
            "confidenceBuckets": bucket_summary,
        },
        "vvsRules": {
            "minimumScoreGap": 0.08,
            "moneylineOnly": True,
            "minimumEdgePct": 3,
            "maximumEdgePct": 25,
            "marketProbabilityMin": 0.30,
            "marketProbabilityMax": 0.75,
            "maxPicksPerDay": 10,
            "paperOnly": True,
            "realMoneyAutoBetting": False,
        },
        "notes": [
            "Do not force picks.",
            "VVS picks require model score gap 8%+.",
            "Sportsbook odds must be connected.",
            "Live edge ledger must be resolved before real-money use.",
            "Pitcher, bullpen, lineup, injury, and weather features are future upgrades.",
        ],
    }

    MODEL_JSON.write_text(json.dumps(model_config, indent=2), encoding="utf-8")
    MODEL_JSON_COPY.write_text(json.dumps(model_config, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 02 CLEAN BASELINE MODEL REPORT")
    lines.append("=" * 48)
    lines.append(f"Completed games: {len(completed)}")
    lines.append("")
    lines.append("Top 10 formulas:")
    for row in grid[:10]:
        lines.append(
            f"Prev {row['previous_record_weight']}% | "
            f"Recent {row['recent_form_weight']}% | "
            f"Pyth {row['pythagorean_weight']}% "
            f"=> Accuracy {row['accuracy']}% | "
            f"tested {row['tested']} | correct {row['correct']}"
        )

    lines.append("")
    lines.append("Selected model:")
    lines.append(
        f"Prev {best['previous_record_weight']}% | "
        f"Recent {best['recent_form_weight']}% | "
        f"Pyth {best['pythagorean_weight']}% "
        f"=> Accuracy {best['accuracy']}%"
    )

    lines.append("")
    lines.append("Confidence gap buckets:")
    for b in bucket_order:
        s = bucket_summary[b]
        lines.append(
            f"{b}: tested={s['tested']} correct={s['correct']} accuracy={s['accuracy']}%"
        )

    lines.append("")
    lines.append("VVS rule:")
    lines.append("Only promote strong picks when model score gap is 8%+ and sportsbook edge is clean.")
    lines.append("")
    lines.append(f"Grid CSV: {GRID_CSV}")
    lines.append(f"Model JSON: {MODEL_JSON}")

    REPORT_TXT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print("DONE")

if __name__ == "__main__":
    main()
