from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "193_patch_calibration_lab_runner_report.txt"

BLOCK = """
Add-Line "Running 189 calibration data readiness..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\189_calibration_data_readiness_audit.py"
Add-Line "189 calibration readiness exit code: $LASTEXITCODE"

Add-Line "Running 190 Moneyline historical calibration..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\190_moneyline_historical_calibration_audit.py"
Add-Line "190 Moneyline historical calibration exit code: $LASTEXITCODE"

Add-Line "Running 191 live pick calibration..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\191_live_pick_calibration_audit.py"
Add-Line "191 live pick calibration exit code: $LASTEXITCODE"

Add-Line "Running 192 calibration control board..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\192_calibration_control_board.py"
Add-Line "192 calibration control board exit code: $LASTEXITCODE"

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER133.exists():
        result = f"MISSING {RUNNER133}"
    else:
        text = RUNNER133.read_text(encoding="utf-8", errors="ignore")
        if "Running 192 calibration control board" in text:
            result = "SKIP already patched"
        else:
            needle = 'Add-Line "ASTRODDS clean daily results runner finished"'
            if needle not in text:
                result = "NEEDLE NOT FOUND"
            else:
                backup = RUNNER133.with_suffix(RUNNER133.suffix + f".before-193-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                shutil.copyfile(RUNNER133, backup)
                RUNNER133.write_text(text.replace(needle, BLOCK + needle), encoding="utf-8")
                result = f"PATCHED 133; backup={backup}"

    lines = [
        "ASTRODDS 193 PATCH CALIBRATION LAB RUNNER",
        "=" * 64,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Result:",
        f"- {result}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
