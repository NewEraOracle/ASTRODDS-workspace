from pathlib import Path
import json
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LOCK_JSON = BASE / "models" / "ASTRODDS_FINAL_PRODUCTION_LOCK.json"
REPORT = BASE / "reports" / "57_final_production_lock_report.txt"

FILES = {
    "runner": BASE / "scripts" / "31_auto_daily_engine_runner.ps1",
    "health_check": BASE / "scripts" / "45_astrodds_health_check.ps1",
    "credit_guard": BASE / "scripts" / "48_credit_guard.py",
    "public_telegram": BASE / "scripts" / "30_telegram_final_engine_alerts.py",
    "review_telegram": BASE / "scripts" / "44_telegram_review_recap.py",
    "proof_log": BASE / "scripts" / "29_public_proof_log.py",
    "feature_parity_audit": BASE / "scripts" / "52_baseballpred_feature_parity_audit.py",
    "source_policy": BASE / "scripts" / "53_official_signal_source_policy.py",
    "odds_roi_audit": BASE / "scripts" / "54_historical_odds_roi_audit.py",
    "real_odds_roi_builder": BASE / "scripts" / "54B_historical_real_odds_roi_builder.py",
    "injury_layer": BASE / "scripts" / "55_injury_impact_layer.py",
    "advanced_metrics": BASE / "scripts" / "56_advanced_pitcher_team_metrics.py",
    "threshold_rules": BASE / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json",
    "source_policy_json": BASE / "models" / "ASTRODDS_OFFICIAL_SIGNAL_SOURCE_POLICY.json",
    "injury_policy": BASE / "models" / "ASTRODDS_INJURY_IMPACT_POLICY.json",
    "advanced_policy": BASE / "models" / "ASTRODDS_ADVANCED_PITCHER_TEAM_METRICS_POLICY.json",
}

RUNTIME = {
    "vvs_final": ROOT / ".astrodds" / "VVS-clean-final-latest.json",
    "engine_final": ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json",
    "signal_ledger": ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json",
    "daily_performance": ROOT / ".astrodds" / "ASTRODDS-daily-performance-latest.json",
    "threshold_context": ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json",
    "telegram_alert_ledger": ROOT / ".astrodds" / "ASTRODDS-telegram-alert-ledger.json",
    "telegram_review_ledger": ROOT / ".astrodds" / "ASTRODDS-telegram-review-recap-ledger.json",
    "credit_guard_ledger": ROOT / ".astrodds" / "ASTRODDS-credit-guard-ledger.json",
    "proof_html": ROOT / "public" / "astrodds-proof-log.html",
    "proof_json": ROOT / "public" / "astrodds-proof-log.json",
}

REPORTS = {
    "39_walk_forward": BASE / "reports" / "39_walk_forward_backtest_report.txt",
    "40_oos_validation": BASE / "reports" / "40_oos_threshold_validation_report.txt",
    "52_feature_parity": BASE / "reports" / "52_baseballpred_feature_parity_audit.json",
    "53_source_policy": BASE / "reports" / "53_official_signal_source_policy_report.txt",
    "54B_real_odds": BASE / "reports" / "54B_historical_real_odds_roi_builder.json",
    "55_injury": BASE / "reports" / "55_injury_impact_layer_report.txt",
    "56_advanced": BASE / "reports" / "56_advanced_pitcher_team_metrics_report.txt",
}

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def read_text(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""

def runtime_count(path):
    if not path.exists():
        return "MISSING"
    if path.suffix.lower() == ".json":
        data = read_json(path, None)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            if isinstance(data.get("rows"), list):
                return len(data.get("rows"))
            return "OK_OBJECT"
        return "BAD_JSON"
    return "OK"

def git_status_short():
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip().splitlines() if result.stdout.strip() else []
    except Exception as e:
        return [f"GIT_STATUS_ERROR: {e}"]

def has_text(path, *needles):
    text = read_text(path)
    return all(n in text for n in needles)

def main():
    generated = datetime.utcnow().isoformat() + "Z"

    source_policy = read_json(FILES["source_policy_json"], {})
    injury_policy = read_json(FILES["injury_policy"], {})
    advanced_policy = read_json(FILES["advanced_policy"], {})
    real_odds = read_json(REPORTS["54B_real_odds"], {})
    threshold_rules = read_json(FILES["threshold_rules"], {})

    file_checks = {name: path.exists() for name, path in FILES.items()}
    report_checks = {name: path.exists() for name, path in REPORTS.items()}
    runtime_counts = {name: runtime_count(path) for name, path in RUNTIME.items()}

    functional_checks = {
        "source_policy_locked": source_policy.get("status") == "OK" and source_policy.get("singleOfficialSourceLocked") is True,
        "public_telegram_official_only": has_text(
            FILES["public_telegram"],
            "ENGINE_BUY",
            "Entry max",
            "5% bankroll",
            "entry_price(r) is not None",
        ),
        "credit_guard_connected": has_text(FILES["runner"], "48_credit_guard.py") and has_text(FILES["health_check"], "Credit guard"),
        "threshold_rules_locked": "lockedThresholds" in threshold_rules and "engineBuyStrictCalibratedProbability" in str(threshold_rules),
        "proof_log_client_ready": RUNTIME["proof_html"].exists() and RUNTIME["proof_json"].exists() and "Client Breakdown" in read_text(RUNTIME["proof_html"]),
        "walk_forward_done": REPORTS["39_walk_forward"].exists() and REPORTS["40_oos_validation"].exists(),
        "feature_parity_audit_done": REPORTS["52_feature_parity"].exists(),
        "injury_policy_exists": FILES["injury_policy"].exists(),
        "advanced_metrics_policy_exists": FILES["advanced_policy"].exists(),
        "real_odds_guard_done": REPORTS["54B_real_odds"].exists(),
    }

    documented_limits = {
        "historical_real_odds_roi": real_odds.get("status", "UNKNOWN"),
        "verified_injury_source_ready": bool(injury_policy.get("verifiedInjuryDatasetReady")),
        "true_advanced_pitcher_dataset_ready": bool(advanced_policy.get("advancedPitcherDatasetReady")),
        "team_context_dataset_ready": bool(advanced_policy.get("teamContextDatasetReady")),
    }

    hard_ready = all(file_checks.values()) and all(report_checks.values()) and all(functional_checks.values())

    limitation_safe = (
        documented_limits["historical_real_odds_roi"] in ["REAL_HISTORICAL_ODDS_MISSING", "REAL_HISTORICAL_ODDS_ROI_READY", "UNKNOWN"]
        and "paper" in str(real_odds).lower()
    )

    if hard_ready and limitation_safe:
        lock_status = "PRODUCTION_LOCK_READY_WITH_DOCUMENTED_LIMITS"
    else:
        lock_status = "REVIEW_NEEDED"

    git_lines = git_status_short()

    lock = {
        "version": "ASTRODDS_FINAL_PRODUCTION_LOCK_V1",
        "generatedAt": generated,
        "status": lock_status,
        "fileChecks": file_checks,
        "reportChecks": report_checks,
        "functionalChecks": functional_checks,
        "runtimeCounts": runtime_counts,
        "documentedLimits": documented_limits,
        "gitStatusShort": git_lines,
        "productionRules": {
            "publicTelegram": "Only ENGINE_BUY A+/A with valid Entry max. No review/watch/wait picks.",
            "stake": "Recommended stake is 5% bankroll in public official buy alerts.",
            "creditGuard": "Default max 3 scans/day and 70 usable scans/month.",
            "proof": "Public proof log is paper/manual tracking only.",
            "realMoneyAutomation": False,
            "marketingLimits": [
                "Do not claim real historical odds ROI until populated historical odds/closing-line data is connected.",
                "Do not claim verified injury intelligence until a verified injury source is connected.",
                "Do not claim xERA/FIP/xFIP until a verified advanced metrics dataset/source is connected.",
            ],
        },
        "nextOptionalImprovements": [
            "Connect populated historical odds/closing-line source.",
            "Connect verified injury source.",
            "Connect Statcast-grade xERA/FIP/xFIP source.",
            "Move runner to VPS/server for always-on production.",
        ],
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    LOCK_JSON.write_text(json.dumps(lock, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 57 FINAL PRODUCTION LOCK REPORT")
    lines.append("=" * 52)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {lock_status}")
    lines.append("")
    lines.append("Core functional checks:")
    for k, v in functional_checks.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Documented limits:")
    for k, v in documented_limits.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Runtime counts:")
    for k, v in runtime_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Production rules:")
    lines.append("- Public Telegram only sends ENGINE_BUY A+/A with valid Entry max.")
    lines.append("- Public Telegram never sends WATCH / WAIT / REVIEW picks.")
    lines.append("- Official alert stake is 5% bankroll.")
    lines.append("- Credit guard protects odds credits.")
    lines.append("- Proof log is client-ready but paper/manual only.")
    lines.append("")
    lines.append("Marketing limits:")
    lines.append("- No real historical odds ROI claim yet.")
    lines.append("- No verified injury-source claim yet.")
    lines.append("- No xERA/FIP/xFIP claim yet.")
    lines.append("")
    lines.append("Git status at report time:")
    if git_lines:
        for line in git_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- CLEAN")
    lines.append("")
    lines.append(f"Lock JSON: {LOCK_JSON}")
    lines.append("")
    lines.append("Rule: final lock only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

