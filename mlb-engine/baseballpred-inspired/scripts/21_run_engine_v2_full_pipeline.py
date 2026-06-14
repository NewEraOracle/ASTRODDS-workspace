from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORT = ROOT / "reports" / "21_engine_v2_full_pipeline_run_report.txt"

PIPELINE = [
    ("08_game_context_snapshot.py", "Game context"),
    ("09_pitcher_context_snapshot.py", "Pitcher context"),
    ("10_bullpen_fatigue_snapshot.py", "Bullpen fatigue"),
    ("16_live_calibrated_edge_gate.py", "Calibrated edge gate"),
    ("17_engine_final_decision.py", "Final engine decision"),
    ("22_odds_snapshot_ledger.py", "Save odds and edge snapshot"),
    ("24_clv_and_line_movement_report.py", "CLV and line movement report"),
    ("25_full_slate_engine.py", "Full slate research engine"),
    ("26_full_slate_strict_gate.py", "Full slate strict gate"),
    ("19_engine_signal_ledger.py", "Save final signals to ledger"),
    ("20_resolve_engine_signal_ledger.py", "Resolve ledger win/loss when games are final"),
    ("29_public_proof_log.py", "Generate public proof log"),
]

def run(script):
    path = SCRIPTS / script

    if not path.exists():
        return False, "", f"Missing script: {path}"

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=360
        )

        return result.returncode == 0, result.stdout, result.stderr

    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        err = str(err) + "\nTIMEOUT: " + script + " took longer than 360 seconds."
        return False, out, err

def main():
    lines = []

    lines.append("ASTRODDS 21 ENGINE V2 FULL PIPELINE RUN REPORT")
    lines.append("=" * 52)
    lines.append(f"Started: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("Goal:")
    lines.append("Run full engine pipeline: context -> calibrated decision -> ledger -> resolver.")
    lines.append("")

    ok_all = True

    for script, name in PIPELINE:
        lines.append(f"STEP — {name}")
        lines.append("-" * 32)
        lines.append(f"Script: {script}")

        print(f"Running: {script} ...", flush=True)

        ok, out, err = run(script)

        lines.append(f"Status: {'OK' if ok else 'FAILED'}")

        if out:
            lines.append("")
            lines.append(out.strip())

        if err:
            lines.append("")
            lines.append("ERRORS:")
            lines.append(err.strip())

        lines.append("")

        if not ok:
            ok_all = False
            break

    lines.append("FINAL STATUS")
    lines.append("=" * 20)
    lines.append(f"Finished: {datetime.utcnow().isoformat()}Z")
    lines.append(f"Pipeline OK: {ok_all}")
    lines.append("")
    lines.append("Final outputs:")
    lines.append(".astrodds/ASTRODDS-engine-final-signals-latest.json")
    lines.append(".astrodds/ASTRODDS-engine-signal-ledger.json")
    lines.append(".astrodds/ASTRODDS-engine-signal-ledger.csv")
    lines.append("")
    lines.append("Rule:")
    lines.append("Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

    if not ok_all:
        sys.exit(1)

if __name__ == "__main__":
    main()

