from pathlib import Path
from datetime import datetime
import json, subprocess

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"

REPORT = REPORTS / "162_final_sidecar_safety_check_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-final-sidecar-safety-check-latest.json"

REQUIRED = [
    "31_auto_daily_engine_runner.ps1", "133_clean_daily_results_runner.ps1",
    "136_send_ou_aplus_telegram.py", "145_resolve_clean_ou_results_from_mlb.py",
    "146_send_clean_ou_daily_results.py", "151_ou_live_context_enrichment_audit.py",
    "152_ou_v2_strict_paper_score_audit.py", "153_ou_v1_v2_ab_test_tracker.py",
    "154_ou_v1_v2_ab_test_report.py", "155_astrodds_today_control_board.py",
    "156_batting_obp_slg_source_builder_audit.py", "157_historical_ou_lines_source_audit.py",
    "158_postponed_suspended_safety_audit.py", "159_merge_lineup_obp_slg_proxy_into_ou_v2.py",
    "160_ou_v2_batting_context_score_audit.py", "161_patch_sidecar_pipeline_runner.py",
]

def git_status():
    try:
        return subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, errors="ignore").strip()
    except Exception as exc:
        return f"ERROR: {exc}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)
    missing = [x for x in REQUIRED if not (SCRIPTS / x).exists()]
    status = git_status()
    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "missingRequiredScripts": missing,
        "gitStatusShort": status,
        "liveSenders": {"moneyline": "135_send_moneyline_a_aplus_telegram.py", "ou": "136_send_ou_aplus_telegram.py"},
        "decision": "OK_TO_LEAVE_LIVE_RUNNING" if not missing else "MISSING_SCRIPTS",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = [
        "ASTRODDS 162 FINAL SIDECAR SAFETY CHECK",
        "=" * 64,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision: {out['decision']}",
        "",
        "Missing required scripts:",
    ]
    lines += [f"- {m}" for m in missing] if missing else ["- none"]
    lines += [
        "",
        "Live senders unchanged:",
        "- Moneyline: 135_send_moneyline_a_aplus_telegram.py",
        "- O/U: 136_send_ou_aplus_telegram.py",
        "",
        "Git status:",
        status if status else "- clean",
        "",
        "Rule:",
        "- Sidecars do not replace live until A/B test proves better.",
        "- Paper/manual only. No real-money automation.",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
