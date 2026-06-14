from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "processed" / "astrodss_master_feature_dataset_v2_calibrated.csv"
OUT_JSON = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "39_walk_forward_backtest.json"
OUT_CSV = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "39_walk_forward_backtest_by_year.csv"
REPORT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "39_walk_forward_backtest_report.txt"

THRESHOLDS = [0.50, 0.55, 0.58, 0.60, 0.63]

def fnum(value, default=None):
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default

def is_true(value):
    return str(value).strip().lower() in ["1", "true", "yes"]

def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def summarize(rows):
    total = len(rows)
    if total == 0:
        return {
            "bets": 0,
            "wins": 0,
            "losses": 0,
            "accuracy": None,
            "paperUnitsEvenMoney": 0,
            "paperRoiEvenMoneyPct": None,
        }

    wins = sum(1 for r in rows if is_true(r.get("model_correct")))
    losses = total - wins
    units = wins - losses
    roi = (units / total) * 100 if total else None

    return {
        "bets": total,
        "wins": wins,
        "losses": losses,
        "accuracy": round(wins / total, 4) if total else None,
        "paperUnitsEvenMoney": units,
        "paperRoiEvenMoneyPct": round(roi, 2) if roi is not None else None,
    }

def main():
    rows = read_rows(INPUT)

    eligible = []
    skipped = 0

    for r in rows:
        prob = fnum(r.get("calibrated_pick_probability_v2"))
        ready = str(r.get("model_ready", "")).strip() == "1"
        model_pick = str(r.get("model_pick", "")).strip()
        winner = str(r.get("winner", "")).strip()

        if not ready or not model_pick or not winner or prob is None:
            skipped += 1
            continue

        item = dict(r)
        item["_prob"] = prob
        eligible.append(item)

    by_threshold = {}
    by_threshold_year = []

    for threshold in THRESHOLDS:
        subset = [r for r in eligible if r["_prob"] >= threshold]
        by_threshold[str(threshold)] = summarize(subset)

        years = sorted(set(int(r["season"]) for r in subset if str(r.get("season", "")).isdigit()))
        for year in years:
            yr_rows = [r for r in subset if int(r["season"]) == year]
            s = summarize(yr_rows)
            by_threshold_year.append({
                "threshold": threshold,
                "season": year,
                **s,
            })

    by_year_all = []
    years = sorted(set(int(r["season"]) for r in eligible if str(r.get("season", "")).isdigit()))
    for year in years:
        yr_rows = [r for r in eligible if int(r["season"]) == year]
        by_year_all.append({
            "threshold": "all_eligible",
            "season": year,
            **summarize(yr_rows),
        })

    full_summary = summarize(eligible)

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "input": str(INPUT),
        "totalRows": len(rows),
        "eligibleRows": len(eligible),
        "skippedRows": skipped,
        "fullEligibleSummary": full_summary,
        "thresholdSummary": by_threshold,
        "byYearAllEligible": by_year_all,
        "byThresholdYear": by_threshold_year,
        "rule": "Historical model validation only. Even-money units are diagnostic, not real sportsbook ROI.",
    }

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["threshold", "season", "bets", "wins", "losses", "accuracy", "paperUnitsEvenMoney", "paperRoiEvenMoneyPct"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in by_year_all + by_threshold_year:
            w.writerow(row)

    lines = []
    lines.append("ASTRODDS 39 WALK-FORWARD BACKTEST REPORT")
    lines.append("=" * 52)
    lines.append(f"Generated: {output['generatedAt']}")
    lines.append("")
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Eligible model rows: {len(eligible)}")
    lines.append(f"Skipped rows: {skipped}")
    lines.append("")
    lines.append("Full eligible summary:")
    lines.append(f"- Bets: {full_summary['bets']}")
    lines.append(f"- Wins: {full_summary['wins']}")
    lines.append(f"- Losses: {full_summary['losses']}")
    lines.append(f"- Accuracy: {round(full_summary['accuracy'] * 100, 2) if full_summary['accuracy'] is not None else 'N/A'}%")
    lines.append(f"- Even-money units: {full_summary['paperUnitsEvenMoney']}u")
    lines.append(f"- Even-money ROI: {full_summary['paperRoiEvenMoneyPct']}%")
    lines.append("")
    lines.append("Threshold summary:")
    for threshold in THRESHOLDS:
        s = by_threshold[str(threshold)]
        acc = round(s["accuracy"] * 100, 2) if s["accuracy"] is not None else "N/A"
        lines.append(
            f"- Prob >= {int(threshold * 100)}% | "
            f"Bets={s['bets']} | Wins={s['wins']} | Losses={s['losses']} | "
            f"Accuracy={acc}% | Units={s['paperUnitsEvenMoney']}u | ROI={s['paperRoiEvenMoneyPct']}%"
        )

    lines.append("")
    lines.append("Year summary, all eligible:")
    for row in by_year_all:
        acc = round(row["accuracy"] * 100, 2) if row["accuracy"] is not None else "N/A"
        lines.append(
            f"- {row['season']} | Bets={row['bets']} | Accuracy={acc}% | "
            f"Units={row['paperUnitsEvenMoney']}u | ROI={row['paperRoiEvenMoneyPct']}%"
        )

    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Important:")
    lines.append("- This is historical model validation.")
    lines.append("- Even-money units are diagnostic only because sportsbook closing odds are not included in this dataset.")
    lines.append("- Next step: compare thresholds and only promote gates that survive 2024/2025/2026 out-of-sample checks.")
    lines.append("")
    lines.append("Rule: audit only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
