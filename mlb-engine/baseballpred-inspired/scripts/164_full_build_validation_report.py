from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, csv, subprocess

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "164_full_build_validation_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-full-build-validation-latest.json"
ET = ZoneInfo("America/New_York")

REQUIRED_SCRIPTS = [
"31_auto_daily_engine_runner.ps1","133_clean_daily_results_runner.ps1","135_send_moneyline_a_aplus_telegram.py","136_send_ou_aplus_telegram.py",
"131_send_clean_moneyline_daily_results.py","132_resolve_clean_moneyline_results_from_mlb.py","145_resolve_clean_ou_results_from_mlb.py","146_send_clean_ou_daily_results.py",
"151_ou_live_context_enrichment_audit.py","152_ou_v2_strict_paper_score_audit.py","153_ou_v1_v2_ab_test_tracker.py","154_ou_v1_v2_ab_test_report.py",
"155_astrodds_today_control_board.py","156_batting_obp_slg_source_builder_audit.py","157_historical_ou_lines_source_audit.py","158_postponed_suspended_safety_audit.py",
"159_merge_lineup_obp_slg_proxy_into_ou_v2.py","160_ou_v2_batting_context_score_audit.py","162_final_sidecar_safety_check.py"]
REQUIRED_FILES = [ASTRO/"ASTRODDS-clean-moneyline-record.csv", ASTRO/"ASTRODDS-clean-ou-record.csv", ASTRO/"ASTRODDS-over-under-expected-total-model-latest.json", ASTRO/"ASTRODDS-ou-v2-strict-paper-score-latest.json"]

def git_status():
    try: return subprocess.check_output(["git","status","--short"], cwd=ROOT, text=True, errors="ignore").strip()
    except Exception as exc: return f"ERROR: {exc}"

def read_csv_rows(path):
    if not path.exists(): return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
    except Exception: return []

def safe_json(path):
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True); ASTRO.mkdir(parents=True, exist_ok=True)
    missing_scripts = [s for s in REQUIRED_SCRIPTS if not (SCRIPTS/s).exists()]
    missing_files = [str(p) for p in REQUIRED_FILES if not p.exists()]
    ml_rows = read_csv_rows(ASTRO/"ASTRODDS-clean-moneyline-record.csv")
    ou_rows = read_csv_rows(ASTRO/"ASTRODDS-clean-ou-record.csv")
    v2 = safe_json(ASTRO/"ASTRODDS-ou-v2-strict-paper-score-latest.json")
    pending_ml = sum(1 for r in ml_rows if str(r.get("result","")).lower() in ("pending","","tbd"))
    pending_ou = sum(1 for r in ou_rows if str(r.get("result","")).lower() in ("pending","","tbd"))
    decision = "FIX_REQUIRED" if missing_scripts or missing_files else "OK_TO_OBSERVE_TOMORROW"
    out = {"generatedAt":datetime.now(ET).isoformat(),"decision":decision,"missingScripts":missing_scripts,"missingFiles":missing_files,"counts":{"moneylineRows":len(ml_rows),"ouRows":len(ou_rows),"pendingMoneyline":pending_ml,"pendingOu":pending_ou,"v2Candidates":len(v2.get("candidates",[])) if isinstance(v2,dict) else 0},"gitStatusShort":git_status()}
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["ASTRODDS 164 FULL BUILD VALIDATION REPORT","="*70,f"Generated ET: {out['generatedAt']}","",f"Decision: {decision}","","Missing scripts:"]
    lines += [f"- {s}" for s in missing_scripts] if missing_scripts else ["- none"]
    lines += ["","Missing files:"] + ([f"- {s}" for s in missing_files] if missing_files else ["- none"])
    lines += ["","Counts:",f"- Moneyline rows: {len(ml_rows)}",f"- O/U rows: {len(ou_rows)}",f"- Pending Moneyline: {pending_ml}",f"- Pending O/U: {pending_ou}",f"- V2 candidates: {out['counts']['v2Candidates']}","","Git status:", out["gitStatusShort"] if out["gitStatusShort"] else "- clean","","Tomorrow checklist:","- Check 133 runner report after 2:30 AM","- Check 131 Moneyline HTML report","- Check 146 O/U HTML report","- Check 154 A/B report","- Check 155 Today Control Board","","Rule:","- Live senders remain 135 and 136.","- Full BaseballPred remains sidecar until A/B test wins.",f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
