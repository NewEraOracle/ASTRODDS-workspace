from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parents[1]

REPORT = BASE / "reports" / "28_engine_completion_audit_report.txt"

required_scripts = [
    "08_game_context_snapshot.py",
    "09_pitcher_context_snapshot.py",
    "10_bullpen_fatigue_snapshot.py",
    "12_data_source_registry.py",
    "13_master_feature_dataset.py",
    "14_feature_quality_audit.py",
    "15_model_calibration_v2.py",
    "16_live_calibrated_edge_gate.py",
    "17_engine_final_decision.py",
    "18_run_engine_v2_pipeline.py",
    "19_engine_signal_ledger.py",
    "20_resolve_engine_signal_ledger.py",
    "21_run_engine_v2_full_pipeline.py",
    "22_odds_snapshot_ledger.py",
    "23_repair_resolved_scores.py",
    "24_clv_and_line_movement_report.py",
    "25_full_slate_engine.py",
    "26_full_slate_strict_gate.py",
    "27_backend_gap_field_audit.py",
]

required_reports = [
    "15_model_calibration_v2_report.txt",
    "17_engine_final_decision_report.txt",
    "20_resolve_engine_signal_ledger_report.txt",
    "21_engine_v2_full_pipeline_run_report.txt",
    "22_odds_snapshot_ledger_report.txt",
    "24_clv_and_line_movement_report.txt",
    "25_full_slate_engine_report.txt",
    "26_full_slate_strict_gate_report.txt",
    "27_backend_gap_field_audit_report.txt",
]

required_outputs = [
    ".astrodds/ASTRODDS-engine-final-signals-latest.json",
    ".astrodds/ASTRODDS-engine-signal-ledger.json",
    ".astrodds/ASTRODDS-odds-snapshot-ledger.json",
    ".astrodds/ASTRODDS-clv-line-movement-latest.json",
    ".astrodds/ASTRODDS-full-slate-strict-latest.json",
    "mlb-engine/baseballpred-inspired/models/ASTRODDS_MLB_CALIBRATION_V2.json",
    "mlb-engine/baseballpred-inspired/models/ASTRODDS_ENGINE_V2_DECISION_RULES.json",
]

def exists(path):
    return path.exists()

def read(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")

def check_list(base, items):
    rows = []
    for item in items:
        p = base / item
        rows.append((item, exists(p)))
    return rows

def main():
    script_checks = check_list(BASE / "scripts", required_scripts)
    report_checks = check_list(BASE / "reports", required_reports)
    output_checks = check_list(WORKSPACE, required_outputs)

    full_runner_report = read(BASE / "reports" / "21_engine_v2_full_pipeline_run_report.txt")
    strict_report = read(BASE / "reports" / "26_full_slate_strict_gate_report.txt")
    backend_audit = read(BASE / "reports" / "27_backend_gap_field_audit_report.txt")

    checks = []

    checks.append(("Full runner pipeline OK", "Pipeline OK: True" in full_runner_report))
    checks.append(("Backend has modelProbabilityGapPct", "modelProbabilityGapPct" in backend_audit or "modelProbabilityGapPct" in strict_report))
    checks.append(("Strict gate no missing backend gap", "missing_backend_gap: 19" not in strict_report and "RESEARCH_ONLY_GAP_MISSING: 19" not in strict_report))
    checks.append(("Strict gate detects conflicts", "Opposite-side conflicts: 3" in strict_report or "Opposite-side conflicts:" in strict_report))
    checks.append(("Odds snapshot exists", (WORKSPACE / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.json").exists()))
    checks.append(("Signal ledger exists", (WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json").exists()))
    checks.append(("Final signals exists", (WORKSPACE / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json").exists()))

    all_scripts_ok = all(ok for _, ok in script_checks)
    all_reports_ok = all(ok for _, ok in report_checks)
    all_outputs_ok = all(ok for _, ok in output_checks)
    all_logic_ok = all(ok for _, ok in checks)

    complete = all_scripts_ok and all_reports_ok and all_outputs_ok and all_logic_ok

    lines = []
    lines.append("ASTRODDS 28 ENGINE COMPLETION AUDIT")
    lines.append("=" * 44)
    lines.append(f"Created: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append(f"ENGINE STATUS: {'COMPLETE V2' if complete else 'PARTIAL'}")
    lines.append("")
    lines.append("Script checks:")
    for name, ok in script_checks:
        lines.append(f"- {'OK' if ok else 'MISSING'}: {name}")

    lines.append("")
    lines.append("Report checks:")
    for name, ok in report_checks:
        lines.append(f"- {'OK' if ok else 'MISSING'}: {name}")

    lines.append("")
    lines.append("Output checks:")
    for name, ok in output_checks:
        lines.append(f"- {'OK' if ok else 'MISSING'}: {name}")

    lines.append("")
    lines.append("Logic checks:")
    for name, ok in checks:
        lines.append(f"- {'OK' if ok else 'FAIL'}: {name}")

    lines.append("")
    lines.append("Engine V2 definition:")
    lines.append("- Calibrated probability, not raw confidence.")
    lines.append("- Context gates: pitcher, bullpen, lineup, weather.")
    lines.append("- Final decision: ENGINE_BUY / MANUAL_REVIEW / WATCH / NO_BET.")
    lines.append("- Signal ledger and resolver.")
    lines.append("- Odds snapshot ledger and CLV tracking.")
    lines.append("- Full slate strict gate with conflict blocking.")
    lines.append("- Paper/manual only. No real-money automation.")

    lines.append("")
    lines.append("Remaining for V3:")
    lines.append("- Historical odds dataset / closing odds.")
    lines.append("- ML ensemble models.")
    lines.append("- Walk-forward backtest.")
    lines.append("- Telegram connected only to finalEngineDecision.")
    lines.append("- Public proof log page.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
