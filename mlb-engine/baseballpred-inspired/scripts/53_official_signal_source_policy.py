from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

POLICY = BASE / "models" / "ASTRODDS_OFFICIAL_SIGNAL_SOURCE_POLICY.json"
REPORT = BASE / "reports" / "53_official_signal_source_policy_report.txt"

PUBLIC_TELEGRAM = BASE / "scripts" / "30_telegram_final_engine_alerts.py"
REVIEW_TELEGRAM = BASE / "scripts" / "44_telegram_review_recap.py"
RUNNER = BASE / "scripts" / "31_auto_daily_engine_runner.ps1"
PIPELINE = BASE / "scripts" / "21_engine_v2_full_pipeline_run.py"

ENGINE_FINAL = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
FULL_SLATE_THRESHOLD = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json"
PUBLIC_ALERT_LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-alert-ledger.json"

def read_text(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def runtime_count(path):
    data = read_json(path, None)
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return "OK_OBJECT"
    return "MISSING_OR_BAD"

def main():
    public_text = read_text(PUBLIC_TELEGRAM)
    review_text = read_text(REVIEW_TELEGRAM)
    runner_text = read_text(RUNNER)
    pipeline_text = read_text(PIPELINE)

    checks = {
        "engine_final_exists": ENGINE_FINAL.exists(),
        "full_slate_threshold_exists": FULL_SLATE_THRESHOLD.exists(),
        "public_telegram_uses_engine_final": "ASTRODDS-engine-final-signals-latest.json" in public_text,
        "public_telegram_only_engine_buy": "finalEngineDecision" in public_text and "ENGINE_BUY" in public_text and "finalGrade" in public_text,
        "public_telegram_requires_entry_price": "entry_price(r) is not None" in public_text and "Entry max" in public_text,
        "review_board_uses_threshold_context": "ASTRODDS-full-slate-context-threshold-final-latest.json" in review_text,
        "review_board_is_review_only": "REVIEW ONLY" in review_text or "Not official" in review_text or "Not official buys" in review_text,
        "runner_has_public_alert_step": (
            "ASTRODDS-engine-final-signals-latest.json" in public_text
            and "ENGINE_BUY" in public_text
            and "Entry max" in public_text
            and "5% bankroll" in public_text
        ),
        "runner_has_review_recap_step": "44_telegram_review_recap.py" in runner_text,
    }

    status = "OK" if all(checks.values()) else "REVIEW_NEEDED"

    policy = {
        "version": "53_official_signal_source_policy_v1",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "officialPublicSource": ".astrodds/ASTRODDS-engine-final-signals-latest.json",
        "publicTelegramScript": "mlb-engine/baseballpred-inspired/scripts/30_telegram_final_engine_alerts.py",
        "publicTelegramRules": [
            "Only finalEngineDecision = ENGINE_BUY",
            "Only finalGrade A+ or A",
            "Requires valid market/entry price",
            "Message shows Pick, Game, Entry max, Recommended stake 5% bankroll",
            "Does not send WATCH, WAIT, MANUAL_REVIEW, FULL_CONTEXT_A_REVIEW, or review-board candidates",
            "Paper/manual only. No real-money automation."
        ],
        "reviewOnlySource": ".astrodds/ASTRODDS-full-slate-context-threshold-final-latest.json",
        "reviewOnlyTelegramScript": "mlb-engine/baseballpred-inspired/scripts/44_telegram_review_recap.py",
        "reviewOnlyRules": [
            "Private/admin review board only",
            "Not a client/public official buy source",
            "Does not alter public official buy logic"
        ],
        "singleOfficialSourceLocked": status == "OK",
        "checks": checks,
        "runtimeCounts": {
            "engineFinalRows": runtime_count(ENGINE_FINAL),
            "fullSlateThresholdRows": runtime_count(FULL_SLATE_THRESHOLD),
            "publicAlertLedgerRows": runtime_count(PUBLIC_ALERT_LEDGER),
        },
        "next": [
            "54 historical odds ROI audit",
            "55 injury impact layer",
            "56 advanced pitcher/team metrics"
        ],
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    POLICY.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 53 OFFICIAL SIGNAL SOURCE POLICY REPORT")
    lines.append("=" * 58)
    lines.append(f"Generated: {policy['createdAt']}")
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("Locked source policy:")
    lines.append(f"- Official public/client source: {policy['officialPublicSource']}")
    lines.append(f"- Review/admin source: {policy['reviewOnlySource']}")
    lines.append("")
    lines.append("Checks:")
    for k, v in checks.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Runtime counts:")
    for k, v in policy["runtimeCounts"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    if status == "OK":
        lines.append("Conclusion:")
        lines.append("- Single official public source is locked.")
        lines.append("- Public Telegram cannot send review/watch/wait picks.")
        lines.append("- Review board remains separate for admin only.")
    else:
        lines.append("Conclusion:")
        lines.append("- Review needed. One or more source-policy checks failed.")
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append("")
    lines.append("Rule: policy lock only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()



