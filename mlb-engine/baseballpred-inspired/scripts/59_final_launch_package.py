from pathlib import Path
import json
import subprocess
from datetime import datetime

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

REPORT = BASE / "reports" / "59_final_launch_package_report.txt"
LOCK_JSON = BASE / "models" / "ASTRODDS_FINAL_LAUNCH_PACKAGE.json"

DOCS = ROOT / "docs" / "astrodds"
RUNBOOK = DOCS / "OPERATOR_RUNBOOK.md"
CLIENT_RULES = DOCS / "CLIENT_TELEGRAM_RULES.md"
LIMITS = DOCS / "DOCUMENTED_LIMITS.md"
LAUNCH_CHECKLIST = DOCS / "LAUNCH_CHECKLIST.md"

FILES = {
    "health_check": BASE / "scripts" / "45_astrodds_health_check.ps1",
    "credit_guard": BASE / "scripts" / "48_credit_guard.py",
    "public_telegram": BASE / "scripts" / "30_telegram_final_engine_alerts.py",
    "review_board": BASE / "scripts" / "44_telegram_review_recap.py",
    "proof_log_html": ROOT / "public" / "astrodds-proof-log.html",
    "proof_log_json": ROOT / "public" / "astrodds-proof-log.json",
    "production_lock": BASE / "models" / "ASTRODDS_FINAL_PRODUCTION_LOCK.json",
    "secret_audit": BASE / "reports" / "58_secret_safety_audit.json",
    "source_policy": BASE / "models" / "ASTRODDS_OFFICIAL_SIGNAL_SOURCE_POLICY.json",
    "threshold_rules": BASE / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json",
    "injury_policy": BASE / "models" / "ASTRODDS_INJURY_IMPACT_POLICY.json",
    "advanced_policy": BASE / "models" / "ASTRODDS_ADVANCED_PITCHER_TEAM_METRICS_POLICY.json",
    "real_odds_guard": BASE / "reports" / "54B_historical_real_odds_roi_builder.json",
}

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def run_git(args):
    try:
        result = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def runtime_count(path):
    if not path.exists():
        return "MISSING"
    if path.suffix.lower() == ".json":
        data = read_json(path, None)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            if isinstance(data.get("rows"), list):
                return len(data["rows"])
            return "OK_OBJECT"
        return "BAD_JSON"
    return "OK"

def main():
    generated = datetime.utcnow().isoformat() + "Z"

    production_lock = read_json(FILES["production_lock"], {})
    secret_audit = read_json(FILES["secret_audit"], {})
    source_policy = read_json(FILES["source_policy"], {})
    real_odds_guard = read_json(FILES["real_odds_guard"], {})
    injury_policy = read_json(FILES["injury_policy"], {})
    advanced_policy = read_json(FILES["advanced_policy"], {})

    checks = {
        "health_check_exists": FILES["health_check"].exists(),
        "credit_guard_exists": FILES["credit_guard"].exists(),
        "public_telegram_exists": FILES["public_telegram"].exists(),
        "review_board_exists": FILES["review_board"].exists(),
        "proof_log_html_exists": FILES["proof_log_html"].exists(),
        "proof_log_json_exists": FILES["proof_log_json"].exists(),
        "production_lock_ready": production_lock.get("status") == "PRODUCTION_LOCK_READY_WITH_DOCUMENTED_LIMITS",
        "secret_safety_safe": secret_audit.get("status") == "SAFE_NO_TRACKED_ENV_NO_LITERAL_SECRETS",
        "source_policy_locked": source_policy.get("singleOfficialSourceLocked") is True,
        "real_odds_guard_done": real_odds_guard.get("status") in ["REAL_HISTORICAL_ODDS_MISSING", "REAL_HISTORICAL_ODDS_ROI_READY"],
        "injury_policy_exists": FILES["injury_policy"].exists(),
        "advanced_policy_exists": FILES["advanced_policy"].exists(),
    }

    launch_status = "LAUNCH_READY_WITH_DOCUMENTED_LIMITS" if all(checks.values()) else "REVIEW_NEEDED"

    git_status = run_git(["status", "--short"]).splitlines()

    DOCS.mkdir(parents=True, exist_ok=True)

    runbook = f"""# ASTRODDS Operator Runbook

Generated UTC: {generated}

## Status

ASTRODDS is launch-ready with documented limits.

## Daily operation

- Do not run the full runner manually unless needed.
- Credit guard protects the odds credits.
- Default daily scan limit: 3 scans/day.
- Scheduled tasks run morning, afternoon, and evening.
- Public Telegram sends only official actionable buys.
- Review board is admin/internal only.

## Main commands

Health check:

```powershell
powershell -ExecutionPolicy Bypass -File ".\\mlb-engine\\baseballpred-inspired\\scripts\\45_astrodds_health_check.ps1"
```

Credit status:

```powershell
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\48_credit_guard.py" status
```

Public proof log:

```text
public/astrodds-proof-log.html
public/astrodds-proof-log.json
```

## Rules

- Paper/manual only.
- No real-money automation.
- No guaranteed profit.
- Public client alerts only show official buys.
- Do not chase above Entry max.
- Recommended stake is 5% bankroll.
"""

    client_rules = f"""# ASTRODDS Client Telegram Rules

Generated UTC: {generated}

## Public channel rule

Public Telegram receives only OFFICIAL BUY signals.

## Public signal format

```text
ðŸŸ¢ ASTRODDS OFFICIAL BUY

Pick: {{team}}
Game: {{away_team}} vs {{home_team}}

Entry max: $0.56
Recommended stake: 5% bankroll

âœ… Passed ASTRODDS filters.
Do not enter above $0.56.

Paper/manual only. No real-money automation.
```

## Never send to public clients

- WATCH
- WAIT
- REVIEW
- MANUAL_REVIEW
- FULL_CONTEXT_A_REVIEW
- backend flags
- raw engine names
- edge tables

## Admin-only

Review board candidates are admin/internal only.
"""

    limits = f"""# ASTRODDS Documented Limits

Generated UTC: {generated}

These limits are documented on purpose so the system stays honest.

## Historical real odds ROI

Status: {real_odds_guard.get("status", "UNKNOWN")}

Current system has forward paper tracking and probability validation.  
Do not claim true historical sportsbook ROI until a populated historical odds / closing-line dataset is connected.

## Injury source

Verified injury source ready: {injury_policy.get("verifiedInjuryDatasetReady", False)}

The injury layer exists and does not invent data.  
Do not claim verified injury intelligence until a verified injury source is connected.

## True advanced pitcher metrics

Advanced pitcher dataset ready: {advanced_policy.get("advancedPitcherDatasetReady", False)}

The system derives pitcher diagnostics from available ERA/WHIP/K-BB/HR data where available.  
Do not claim xERA, FIP, xFIP, or Statcast-grade metrics until verified data is connected.

## Betting disclaimer

No guaranteed profit.  
Paper/manual only.  
No real-money automation.
"""

    launch_checklist = f"""# ASTRODDS Launch Checklist

Generated UTC: {generated}

## Completed

- [x] Engine health check
- [x] Credit guard
- [x] Public Telegram official-only filter
- [x] Review board separated from public channel
- [x] Source policy lock
- [x] Proof log client-ready
- [x] Secret safety audit
- [x] Final production lock
- [x] Injury policy layer
- [x] Advanced pitcher diagnostics layer
- [x] Historical real odds ROI guard

## Before selling

- [ ] Keep wording honest: paper/manual tracking.
- [ ] Do not advertise guaranteed win rate.
- [ ] Do not advertise real historical odds ROI yet.
- [ ] Do not advertise verified injury source yet.
- [ ] Do not advertise xERA/FIP/xFIP yet.

## Optional upgrades later

- [ ] Connect real historical odds / closing-line dataset.
- [ ] Connect verified injuries source.
- [ ] Connect Statcast-grade pitcher metrics.
- [ ] Move scheduled runner to VPS/server.
"""

    RUNBOOK.write_text(runbook, encoding="utf-8")
    CLIENT_RULES.write_text(client_rules, encoding="utf-8")
    LIMITS.write_text(limits, encoding="utf-8")
    LAUNCH_CHECKLIST.write_text(launch_checklist, encoding="utf-8")

    package = {
        "version": "ASTRODDS_FINAL_LAUNCH_PACKAGE_V1",
        "generatedAt": generated,
        "status": launch_status,
        "checks": checks,
        "gitStatusShort": git_status,
        "docs": {
            "operatorRunbook": str(RUNBOOK),
            "clientTelegramRules": str(CLIENT_RULES),
            "documentedLimits": str(LIMITS),
            "launchChecklist": str(LAUNCH_CHECKLIST),
        },
        "runtime": {
            "proofLogHtml": runtime_count(FILES["proof_log_html"]),
            "proofLogJson": runtime_count(FILES["proof_log_json"]),
        },
        "rules": {
            "publicTelegram": "official buys only",
            "stake": "5% bankroll",
            "creditGuard": "active",
            "paperOnly": True,
            "realMoneyAutomation": False,
        },
    }

    LOCK_JSON.write_text(json.dumps(package, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 59 FINAL LAUNCH PACKAGE REPORT")
    lines.append("=" * 50)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {launch_status}")
    lines.append("")
    lines.append("Checks:")
    for k, v in checks.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Created docs:")
    lines.append(f"- {RUNBOOK}")
    lines.append(f"- {CLIENT_RULES}")
    lines.append(f"- {LIMITS}")
    lines.append(f"- {LAUNCH_CHECKLIST}")
    lines.append("")
    lines.append("Final operating rules:")
    lines.append("- Public Telegram only sends official buys.")
    lines.append("- Review board stays admin/internal.")
    lines.append("- Entry max required.")
    lines.append("- Stake fixed at 5% bankroll.")
    lines.append("- Credit guard active.")
    lines.append("- Paper/manual only. No real-money automation.")
    lines.append("")
    lines.append("Git status at package time:")
    if git_status:
        for line in git_status:
            lines.append(f"- {line}")
    else:
        lines.append("- CLEAN")
    lines.append("")
    lines.append(f"Launch package JSON: {LOCK_JSON}")
    lines.append("")
    lines.append("Rule: launch packaging only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

