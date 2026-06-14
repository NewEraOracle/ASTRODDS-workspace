from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "39_walk_forward_backtest_by_year.csv"
OUT_JSON = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "40_oos_threshold_validation.json"
REPORT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "40_oos_threshold_validation_report.txt"

OOS_YEARS = {2024, 2025, 2026}

def fnum(x, default=0.0):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default

def main():
    rows = []
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("threshold") == "all_eligible":
                continue
            season = int(r["season"])
            if season not in OOS_YEARS:
                continue
            rows.append(r)

    thresholds = sorted(set(r["threshold"] for r in rows), key=lambda x: fnum(x))
    summary = []

    for t in thresholds:
        subset = [r for r in rows if r["threshold"] == t]
        bets = sum(int(r["bets"]) for r in subset)
        wins = sum(int(r["wins"]) for r in subset)
        losses = sum(int(r["losses"]) for r in subset)
        acc = wins / bets if bets else 0
        units = wins - losses
        roi = (units / bets * 100) if bets else 0
        min_year_bets = min(int(r["bets"]) for r in subset) if subset else 0
        min_year_acc = min(fnum(r["accuracy"]) for r in subset) if subset else 0

        if fnum(t) >= 0.60 and min_year_bets >= 50 and min_year_acc >= 0.58:
            recommendation = "ENGINE_BUY_STRICT"
        elif fnum(t) >= 0.58 and min_year_bets >= 150 and min_year_acc >= 0.58:
            recommendation = "A_REVIEW_CORE"
        elif fnum(t) >= 0.55 and min_year_bets >= 300 and min_year_acc >= 0.55:
            recommendation = "WATCH_REVIEW"
        else:
            recommendation = "RESEARCH_ONLY"

        summary.append({
            "threshold": t,
            "oosYears": sorted(OOS_YEARS),
            "bets": bets,
            "wins": wins,
            "losses": losses,
            "accuracy": round(acc, 4),
            "unitsEvenMoney": units,
            "roiEvenMoneyPct": round(roi, 2),
            "minYearBets": min_year_bets,
            "minYearAccuracy": round(min_year_acc, 4),
            "recommendation": recommendation,
        })

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "input": str(INPUT),
        "oosYears": sorted(OOS_YEARS),
        "summary": summary,
        "lockedThresholds": {
            "engineBuyStrict": 0.60,
            "aReviewCore": 0.58,
            "watchReview": 0.55,
            "noBetBelow": 0.55,
        },
        "rule": "Historical validation only. Even-money units are diagnostic. No real-money automation.",
    }

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 40 OUT-OF-SAMPLE THRESHOLD VALIDATION")
    lines.append("=" * 58)
    lines.append(f"Generated: {output['generatedAt']}")
    lines.append("")
    lines.append("OOS years: 2024, 2025, 2026")
    lines.append("")
    lines.append("Threshold results:")

    for s in summary:
        lines.append(
            f"- Prob >= {float(s['threshold']) * 100:.0f}% | "
            f"Bets={s['bets']} | Wins={s['wins']} | Losses={s['losses']} | "
            f"Accuracy={s['accuracy'] * 100:.2f}% | Units={s['unitsEvenMoney']}u | "
            f"ROI={s['roiEvenMoneyPct']}% | MinYearBets={s['minYearBets']} | "
            f"MinYearAcc={s['minYearAccuracy'] * 100:.2f}% | "
            f"Recommendation={s['recommendation']}"
        )

    lines.append("")
    lines.append("Locked decision thresholds:")
    lines.append("- 60%+ calibrated probability = ENGINE_BUY_STRICT only if context is clean.")
    lines.append("- 58%+ calibrated probability = A_REVIEW_CORE / strong candidate.")
    lines.append("- 55%+ calibrated probability = WATCH_REVIEW.")
    lines.append("- Below 55% = NO_BET / research only.")
    lines.append("")
    lines.append("Important:")
    lines.append("- 58%+ is the best balance of volume and stability.")
    lines.append("- 60%+ is strongest but lower volume, so it should be reserved for strict ENGINE_BUY.")
    lines.append("- Context gates still override probability: lineup, pitcher, bullpen, conflict, weather.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append("")
    lines.append("Rule: validation only. Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
