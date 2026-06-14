from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "40_oos_threshold_validation.json"
OUT = ROOT / "mlb-engine" / "baseballpred-inspired" / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json"
REPORT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "41_threshold_rules_lock_report.txt"

def main():
    data = json.loads(INPUT.read_text(encoding="utf-8-sig"))

    rules = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "source": str(INPUT),
        "version": "ASTRODDS_ENGINE_V2_THRESHOLDS_2026_06",
        "paperOnly": True,
        "lockedThresholds": {
            "engineBuyStrictCalibratedProbability": 0.60,
            "aReviewCoreCalibratedProbability": 0.58,
            "watchReviewCalibratedProbability": 0.55,
            "noBetBelowCalibratedProbability": 0.55
        },
        "contextOverrides": {
            "oppositeSideConflict": "BLOCK",
            "pickedPitcherStatsMissing": "BLOCK",
            "pickedPitcherHighEra": "BLOCK_OR_REVIEW",
            "pickedPitcherHighWhip": "BLOCK_OR_REVIEW",
            "pickedBullpenHighFatigue": "BLOCK_OR_REVIEW",
            "lineupNotConfirmed": "REVIEW_ONLY",
            "highWindWeather": "REVIEW_ONLY"
        },
        "decisionMap": {
            "probability60PlusAndCleanContext": "ENGINE_BUY",
            "probability58Plus": "MANUAL_REVIEW_A",
            "probability55Plus": "WATCH_REVIEW",
            "below55": "NO_BET"
        },
        "oosValidation": data.get("summary", []),
        "notes": [
            "60%+ is strongest but lower volume; reserve for strict ENGINE_BUY only when context is clean.",
            "58%+ is the best balance of volume and stability for A review.",
            "55%+ can remain watch/review.",
            "Context gates override probability.",
            "No real-money automation."
        ]
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rules, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 41 THRESHOLD RULES LOCK REPORT")
    lines.append("=" * 52)
    lines.append("Status: OK")
    lines.append("")
    lines.append("Locked thresholds:")
    lines.append("- 60%+ calibrated probability = ENGINE_BUY strict if context clean")
    lines.append("- 58%+ calibrated probability = A review core")
    lines.append("- 55%+ calibrated probability = watch/review")
    lines.append("- Below 55% = no bet")
    lines.append("")
    lines.append(f"Rules JSON: {OUT}")
    lines.append("")
    lines.append("Rule: paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
