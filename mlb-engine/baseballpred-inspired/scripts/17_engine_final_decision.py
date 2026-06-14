from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

INPUT = WORKSPACE / ".astrodds" / "VVS-calibrated-edge-latest.json"

OUT_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
OUT_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-engine-final-signals-latest.csv"
REPORT = ROOT / "reports" / "17_engine_final_decision_report.txt"
MODEL = ROOT / "models" / "ASTRODDS_ENGINE_V2_DECISION_RULES.json"
THRESHOLD_RULES = ROOT / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json"

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def read_threshold_rules():
    if not THRESHOLD_RULES.exists():
        return {
            "version": "missing",
            "lockedThresholds": {
                "engineBuyStrictCalibratedProbability": 0.60,
                "aReviewCoreCalibratedProbability": 0.58,
                "watchReviewCalibratedProbability": 0.55,
            },
        }

    try:
        return json.loads(THRESHOLD_RULES.read_text(encoding="utf-8-sig"))
    except Exception:
        return {
            "version": "invalid",
            "lockedThresholds": {
                "engineBuyStrictCalibratedProbability": 0.60,
                "aReviewCoreCalibratedProbability": 0.58,
                "watchReviewCalibratedProbability": 0.55,
            },
        }


def calibrated_pick_probability(row):
    return (
        fnum(row.get("calibratedProbabilityV2"))
        or fnum(row.get("calibratedProbability"))
        or fnum(row.get("calibrated_pick_probability_v2"))
        or 0
    )


def locked_engine_buy_min():
    rules = read_threshold_rules()
    thresholds = rules.get("lockedThresholds", {})
    return fnum(thresholds.get("engineBuyStrictCalibratedProbability")) or 0.60


def threshold_rule_version():
    return read_threshold_rules().get("version", "missing")


def clean_flags(flags):
    if not flags or flags == "none":
        return "none"

    mapping = {
        "away_pitcher_high_era": "away starting pitcher high ERA",
        "away_pitcher_high_whip": "away starting pitcher high WHIP",
        "home_pitcher_high_era": "home starting pitcher high ERA",
        "home_pitcher_high_whip": "home starting pitcher high WHIP",
        "away_pitcher_stats_missing": "away pitcher stats missing",
        "home_pitcher_stats_missing": "home pitcher stats missing",
        "away_bullpen_high_fatigue": "away bullpen high fatigue",
        "home_bullpen_high_fatigue": "home bullpen high fatigue",
        "away_bullpen_medium_fatigue": "away bullpen medium fatigue",
        "home_bullpen_medium_fatigue": "home bullpen medium fatigue",
    }

    out = []
    for p in str(flags).split("|"):
        if p:
            out.append(mapping.get(p, p.replace("_", " ")))

    return ", ".join(out) if out else "none"

def quality_grade(row):
    edge = fnum(row.get("calibratedEdgePct")) or 0
    decision = row.get("calibratedDecision", "")
    warnings = []

    if str(row.get("bullpenContextFlags", "none")) != "none":
        warnings.append("bullpen")
    if str(row.get("pitcherContextFlags", "none")) != "none":
        warnings.append("pitcher")
    if row.get("awayLineupStatus") != "confirmed" or row.get("homeLineupStatus") != "confirmed":
        warnings.append("lineup")

    if decision == "vvs_buy" and edge >= 7 and not warnings:
        return "A+"

    if decision in ["vvs_buy", "manual_review"] and edge >= 7:
        return "A"

    if decision in ["small_buy", "manual_review"] and edge >= 4:
        return "B"

    if decision == "watch":
        return "WATCH"

    return "NO_BET"

def final_decision(row):
    edge = fnum(row.get("calibratedEdgePct")) or 0
    decision = row.get("calibratedDecision", "")
    grade = quality_grade(row)

    risk_notes = []

    if str(row.get("bullpenContextFlags", "none")) != "none":
        risk_notes.append("bullpen warning")

    if str(row.get("pitcherContextFlags", "none")) != "none":
        risk_notes.append("pitcher warning")

    if row.get("awayLineupStatus") != "confirmed" or row.get("homeLineupStatus") != "confirmed":
        risk_notes.append("lineup not fully confirmed")

    # strict official buy rule
    # ENGINE_BUY now requires:
    # - validated calibrated probability threshold from ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json
    # - positive calibrated edge
    # - clean context
    # - no real-money automation
    prob = calibrated_pick_probability(row)
    engine_buy_min = locked_engine_buy_min()
    threshold_passed = prob >= engine_buy_min

    if decision in ["vvs_buy", "manual_review"] and edge >= 7 and threshold_passed and not risk_notes:
        return (
            "ENGINE_BUY",
            grade,
            f"Clean calibrated edge with validated threshold passed: probability {round(prob * 100, 2)}% >= {round(engine_buy_min * 100, 2)}%."
        )

    # manual review rule
    if edge >= 3 and decision in ["manual_review", "small_buy", "vvs_buy"]:
        return "MANUAL_REVIEW", grade, "Calibrated edge exists, but review required: " + (", ".join(risk_notes) if risk_notes else "small edge.")

    # watch rule
    if decision == "watch" or edge < 3:
        return "WATCH", grade, "No clean calibrated edge after calibration."

    return "NO_BET", "NO_BET", "Rejected by final engine rules."

def existing_model_created_at():
    if MODEL.exists():
        try:
            existing = json.loads(MODEL.read_text(encoding="utf-8-sig"))
            value = existing.get("createdAt")
            if value:
                return value
        except Exception:
            pass

    return datetime.utcnow().isoformat() + "Z"


def write_model_rules_if_changed(model_rules):
    model_text = json.dumps(model_rules, indent=2)

    if MODEL.exists():
        try:
            existing_text = MODEL.read_text(encoding="utf-8-sig")
            if existing_text.strip() == model_text.strip():
                return False
        except Exception:
            pass

    MODEL.write_text(model_text, encoding="utf-8")
    return True


def main():
    rows = read_json(INPUT)

    final_rows = []
    counts = {}

    for row in rows:
        r = dict(row)

        decision, grade, reason = final_decision(r)

        r["engineVersion"] = "ASTRODDS_ENGINE_V2_CALIBRATED_CONTEXT"
        r["finalEngineDecision"] = decision
        r["finalGrade"] = grade
        r["finalReason"] = reason
        r["thresholdRuleVersion"] = threshold_rule_version()
        r["lockedEngineBuyProbabilityMin"] = locked_engine_buy_min()
        r["calibratedPickProbabilityForThreshold"] = calibrated_pick_probability(r)
        r["officialBuyThresholdPassed"] = calibrated_pick_probability(r) >= locked_engine_buy_min()
        r["humanPitcherWarnings"] = clean_flags(r.get("pitcherContextFlags"))
        r["humanBullpenWarnings"] = clean_flags(r.get("bullpenContextFlags"))
        r["generatedAt"] = datetime.utcnow().isoformat() + "Z"
        r["paperOnly"] = True
        r["realMoneyApproved"] = False

        counts[decision] = counts.get(decision, 0) + 1
        final_rows.append(r)

    order = {
        "ENGINE_BUY": 0,
        "MANUAL_REVIEW": 1,
        "WATCH": 2,
        "NO_BET": 3
    }

    final_rows.sort(
        key=lambda x: (
            order.get(x.get("finalEngineDecision"), 9),
            -(fnum(x.get("calibratedEdgePct")) or 0)
        )
    )

    OUT_JSON.write_text(json.dumps(final_rows, indent=2), encoding="utf-8")

    fields = sorted({k for r in final_rows for k in r.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(final_rows)

    model_rules = {
        "engineName": "ASTRODDS_ENGINE_V2_CALIBRATED_CONTEXT",
        "createdAt": existing_model_created_at(),
        "mode": "paper_only",
        "realMoneyApproved": False,
        "decisionRules": {
            "ENGINE_BUY": "calibrated probability >= locked 60% threshold, calibrated edge >= 7%, clean context, no major warnings",
            "MANUAL_REVIEW": "calibrated edge >= 3% but context warnings or smaller grade",
            "WATCH": "calibrated edge < 3% or weak post-calibration signal",
            "NO_BET": "rejected by final rules"
        },
        "principles": [
            "Raw model probability is never used for final edge.",
            "Calibrated probability controls edge.",
            "Pitcher, bullpen, lineup, and weather are context gates, not model weights yet.",
            "No auto real-money betting.",
            "Edge ledger must prove live results before risk escalation."
        ]
    }

    model_rules_written = write_model_rules_if_changed(model_rules)

    lines = []
    lines.append("ASTRODDS 17 FINAL ENGINE DECISION REPORT")
    lines.append("=" * 46)
    lines.append("")
    lines.append("Goal:")
    lines.append("Create final engine signal file using calibrated edge + context gates.")
    lines.append("")
    lines.append(f"Input rows: {len(rows)}")
    lines.append("")
    lines.append("Decision counts:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Final engine signals:")

    for r in final_rows:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Final={r.get('finalEngineDecision')} | Grade={r.get('finalGrade')} | "
            f"Market={round((fnum(r.get('marketProbability')) or 0) * 100, 2)}% | "
            f"Calibrated={round((fnum(r.get('calibratedProbabilityV2')) or 0) * 100, 2)}% | "
            f"CalEdge={r.get('calibratedEdgePct')}% | "
            f"Reason={r.get('finalReason')}"
        )

    lines.append("")
    lines.append("Important:")
    lines.append("- There are no automatic real-money bets.")
    lines.append("- ENGINE_BUY requires clean calibrated edge and clean context.")
    lines.append("- MANUAL_REVIEW means the bot sees edge but risk context is not clean.")
    lines.append("- WATCH means the raw pick did not survive calibration.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"Model rules: {MODEL}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()


