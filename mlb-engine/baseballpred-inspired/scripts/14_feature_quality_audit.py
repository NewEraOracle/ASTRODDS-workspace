from pathlib import Path
import csv
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "astrodss_master_feature_dataset_v1.csv"
REPORT = ROOT / "reports" / "14_feature_quality_audit_report.txt"
OUT_JSON = ROOT / "reports" / "14_feature_quality_audit.json"

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def load_rows():
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def eval_feature(rows, name, away_col, home_col, higher_is_better=True, min_gap=0.0):
    tested = 0
    correct = 0
    missing = 0
    ties = 0

    for r in rows:
        away = fnum(r.get(away_col))
        home = fnum(r.get(home_col))
        winner = r.get("winner")
        away_team = r.get("away_team")
        home_team = r.get("home_team")

        if away is None or home is None:
            missing += 1
            continue

        diff = away - home

        if abs(diff) < min_gap:
            ties += 1
            continue

        if higher_is_better:
            pick = away_team if away > home else home_team
        else:
            pick = away_team if away < home else home_team

        tested += 1
        if pick == winner:
            correct += 1

    acc = round((correct / tested) * 100, 2) if tested else 0

    return {
        "feature": name,
        "tested": tested,
        "correct": correct,
        "missing": missing,
        "tiesSkipped": ties,
        "accuracy": acc,
        "awayCol": away_col,
        "homeCol": home_col,
        "higherIsBetter": higher_is_better,
        "minGap": min_gap,
    }

def eval_model_bucket(rows):
    buckets = defaultdict(lambda: {"tested": 0, "correct": 0})

    for r in rows:
        if str(r.get("model_ready")) != "1":
            continue

        bucket = r.get("model_score_gap_bucket", "missing")
        correct = int(r.get("model_correct") or 0)

        buckets[bucket]["tested"] += 1
        buckets[bucket]["correct"] += correct

    out = {}
    for b, s in buckets.items():
        tested = s["tested"]
        correct = s["correct"]
        acc = round((correct / tested) * 100, 2) if tested else 0
        out[b] = {"tested": tested, "correct": correct, "accuracy": acc}

    return out

def eval_filters(rows):
    filters = {
        "model_gap_8_plus": lambda r: fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.08,
        "model_gap_5_plus": lambda r: fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.05,
        "model_gap_3_plus": lambda r: fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.03,
        "model_gap_8_plus_and_rest_edge": lambda r: (
            fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.08
            and fnum(r.get("away_rest_days")) is not None
            and fnum(r.get("home_rest_days")) is not None
            and abs(fnum(r.get("away_rest_days")) - fnum(r.get("home_rest_days"))) >= 1
        ),
        "model_gap_8_plus_and_recent_rd_edge": lambda r: (
            fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.08
            and fnum(r.get("away_recent10_run_diff_pg")) is not None
            and fnum(r.get("home_recent10_run_diff_pg")) is not None
            and abs(fnum(r.get("away_recent10_run_diff_pg")) - fnum(r.get("home_recent10_run_diff_pg"))) >= 0.5
        ),
        "model_gap_8_plus_and_pitcher_history_available": lambda r: (
            fnum(r.get("model_score_gap")) is not None and fnum(r.get("model_score_gap")) >= 0.08
            and fnum(r.get("away_pitcher_prior_starts")) is not None
            and fnum(r.get("home_pitcher_prior_starts")) is not None
            and fnum(r.get("away_pitcher_prior_starts")) >= 5
            and fnum(r.get("home_pitcher_prior_starts")) >= 5
        ),
    }

    results = {}

    for name, fn in filters.items():
        tested = 0
        correct = 0

        for r in rows:
            if str(r.get("model_ready")) != "1":
                continue

            if not fn(r):
                continue

            tested += 1
            correct += int(r.get("model_correct") or 0)

        acc = round((correct / tested) * 100, 2) if tested else 0
        results[name] = {"tested": tested, "correct": correct, "accuracy": acc}

    return results

def coverage(rows, columns):
    out = {}
    total = len(rows)

    for c in columns:
        present = sum(1 for r in rows if r.get(c) not in [None, ""])
        out[c] = {
            "present": present,
            "missing": total - present,
            "coveragePct": round((present / total) * 100, 2) if total else 0
        }

    return out

def main():
    rows = load_rows()

    feature_tests = [
        eval_feature(rows, "Previous season win pct", "away_prev_win_pct", "home_prev_win_pct", True),
        eval_feature(rows, "Previous season Pythagorean", "away_prev_pyth", "home_prev_pyth", True),
        eval_feature(rows, "Previous season run diff", "away_prev_run_diff_pg", "home_prev_run_diff_pg", True),
        eval_feature(rows, "Previous season home/away split", "away_prev_away_win_pct", "home_prev_home_win_pct", True),
        eval_feature(rows, "Recent 10 win pct", "away_recent10_win_pct", "home_recent10_win_pct", True),
        eval_feature(rows, "Recent 10 run diff", "away_recent10_run_diff_pg", "home_recent10_run_diff_pg", True),
        eval_feature(rows, "Recent 10 runs for", "away_recent10_runs_for", "home_recent10_runs_for", True),
        eval_feature(rows, "Recent 10 runs against", "away_recent10_runs_against", "home_recent10_runs_against", False),
        eval_feature(rows, "Rest days", "away_rest_days", "home_rest_days", True, min_gap=1),
        eval_feature(rows, "Pitcher prior team win pct", "away_pitcher_prior_team_win_pct", "home_pitcher_prior_team_win_pct", True),
        eval_feature(rows, "Pitcher prior avg IP", "away_pitcher_prior_avg_ip", "home_pitcher_prior_avg_ip", True),
    ]

    feature_tests_sorted = sorted(feature_tests, key=lambda x: x["accuracy"], reverse=True)

    important_cols = [
        "away_prev_win_pct",
        "home_prev_win_pct",
        "away_prev_pyth",
        "home_prev_pyth",
        "away_recent10_win_pct",
        "home_recent10_win_pct",
        "away_recent10_run_diff_pg",
        "home_recent10_run_diff_pg",
        "away_rest_days",
        "home_rest_days",
        "away_pitcher_prior_team_win_pct",
        "home_pitcher_prior_team_win_pct",
        "away_pitcher_prior_avg_ip",
        "home_pitcher_prior_avg_ip",
        "model_score_gap",
        "model_correct",
    ]

    bucket_results = eval_model_bucket(rows)
    filter_results = eval_filters(rows)
    coverage_results = coverage(rows, important_cols)

    results = {
        "rows": len(rows),
        "featureTests": feature_tests_sorted,
        "bucketResults": bucket_results,
        "filterResults": filter_results,
        "coverage": coverage_results,
    }

    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 14 FEATURE QUALITY AUDIT")
    lines.append("=" * 38)
    lines.append(f"Rows: {len(rows)}")
    lines.append("")
    lines.append("Feature standalone accuracy:")
    for r in feature_tests_sorted:
        lines.append(
            f"- {r['feature']}: accuracy={r['accuracy']}% tested={r['tested']} "
            f"missing={r['missing']} tiesSkipped={r['tiesSkipped']}"
        )

    lines.append("")
    lines.append("Model score gap buckets:")
    for b in ["0-1%", "1-2%", "2-3%", "3-5%", "5-8%", "8%+"]:
        s = bucket_results.get(b, {"tested": 0, "correct": 0, "accuracy": 0})
        lines.append(f"- {b}: accuracy={s['accuracy']}% tested={s['tested']} correct={s['correct']}")

    lines.append("")
    lines.append("Filter tests:")
    for name, s in filter_results.items():
        lines.append(f"- {name}: accuracy={s['accuracy']}% tested={s['tested']} correct={s['correct']}")

    lines.append("")
    lines.append("Feature coverage:")
    for c, s in coverage_results.items():
        lines.append(f"- {c}: coverage={s['coveragePct']}% present={s['present']} missing={s['missing']}")

    lines.append("")
    lines.append("Engine conclusion:")
    lines.append("- Model score gap remains the strongest current filter.")
    lines.append("- Pitcher prior history has low coverage and should not control picks yet.")
    lines.append("- Next step is calibration: convert raw model scores into calibrated win probabilities.")
    lines.append("- After calibration, test edge against market probability and track ROI.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
