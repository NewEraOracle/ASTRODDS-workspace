from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORT = ROOT / "reports" / "18_engine_v2_pipeline_run_report.txt"

PIPELINE = [
    {
        "step": "08",
        "name": "Game context snapshot",
        "script": "08_game_context_snapshot.py",
        "purpose": "Connect probable pitchers, lineups, venue, weather, and game status."
    },
    {
        "step": "09",
        "name": "Pitcher context snapshot",
        "script": "09_pitcher_context_snapshot.py",
        "purpose": "Add ERA, WHIP, IP, strikeouts, walks, and pitcher warning flags."
    },
    {
        "step": "10",
        "name": "Bullpen fatigue snapshot",
        "script": "10_bullpen_fatigue_snapshot.py",
        "purpose": "Estimate bullpen fatigue from previous 1 / 3 / 7 days."
    },
    {
        "step": "16",
        "name": "Live calibrated edge gate",
        "script": "16_live_calibrated_edge_gate.py",
        "purpose": "Replace raw model probability with calibrated historical probability."
    },
    {
        "step": "17",
        "name": "Final engine decision",
        "script": "17_engine_final_decision.py",
        "purpose": "Create final ENGINE_BUY / MANUAL_REVIEW / WATCH / NO_BET signals."
    }
]

def run_script(script_name):
    script_path = SCRIPTS / script_name

    if not script_path.exists():
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Missing script: {script_path}"
        }

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True
    )

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def main():
    started = datetime.utcnow().isoformat() + "Z"
    lines = []

    lines.append("ASTRODDS 18 ENGINE V2 PIPELINE RUN REPORT")
    lines.append("=" * 48)
    lines.append(f"Started: {started}")
    lines.append("")
    lines.append("Goal:")
    lines.append("Run the live engine pipeline from context enrichment to final calibrated decision signals.")
    lines.append("")

    all_ok = True

    for item in PIPELINE:
        lines.append(f"STEP {item['step']} — {item['name']}")
        lines.append("-" * 40)
        lines.append(f"Script: {item['script']}")
        lines.append(f"Purpose: {item['purpose']}")

        result = run_script(item["script"])

        if result["ok"]:
            lines.append("Status: OK")
        else:
            lines.append("Status: FAILED")
            all_ok = False

        lines.append(f"Return code: {result['returncode']}")

        if result["stdout"]:
            lines.append("")
            lines.append("Output:")
            lines.append(result["stdout"].strip())

        if result["stderr"]:
            lines.append("")
            lines.append("Errors:")
            lines.append(result["stderr"].strip())

        lines.append("")

        if not result["ok"]:
            break

    finished = datetime.utcnow().isoformat() + "Z"

    lines.append("FINAL STATUS")
    lines.append("=" * 20)
    lines.append(f"Finished: {finished}")
    lines.append(f"Pipeline OK: {all_ok}")
    lines.append("")
    lines.append("Final engine outputs:")
    lines.append(".astrodds/ASTRODDS-engine-final-signals-latest.json")
    lines.append(".astrodds/ASTRODDS-engine-final-signals-latest.csv")
    lines.append("mlb-engine/baseballpred-inspired/reports/17_engine_final_decision_report.txt")
    lines.append("")
    lines.append("Rule:")
    lines.append("Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
