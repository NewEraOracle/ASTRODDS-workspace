from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER = SCRIPTS / "31_auto_daily_engine_runner.ps1"
REPORT = REPORTS / "208_patch_moneyline_first_board_runner_report.txt"

BLOCK = """
Add-Line "Running fixed Moneyline BaseballPred full slate board..."
$mlFullSlateFixed = Join-Path $ScriptDir "206_moneyline_baseballpred_full_slate_fixed.py"
if (Test-Path $mlFullSlateFixed) {
  $mlFullSlateFixedProcess = Start-Process python -ArgumentList "`"$mlFullSlateFixed`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Fixed Moneyline full slate board exit code: $($mlFullSlateFixedProcess.ExitCode)"
} else {
  Add-Line "Fixed Moneyline full slate board skipped: script not found."
}

Add-Line "Running Moneyline-first full slate board report..."
$mlFirstBoardReport = Join-Path $ScriptDir "207_full_slate_game_board_moneyline_first_report.py"
if (Test-Path $mlFirstBoardReport) {
  $mlFirstBoardReportProcess = Start-Process python -ArgumentList "`"$mlFirstBoardReport`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline-first board report exit code: $($mlFirstBoardReportProcess.ExitCode)"
} else {
  Add-Line "Moneyline-first board report skipped: script not found."
}

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER.exists():
        result = f"MISSING {RUNNER}"
    else:
        text = RUNNER.read_text(encoding="utf-8", errors="ignore")
        if "Running fixed Moneyline BaseballPred full slate board" in text:
            result = "SKIP already patched"
        else:
            needle = "Running Telegram result tracking"
            idx = text.find(needle)
            if idx == -1:
                result = "NEEDLE NOT FOUND"
            else:
                backup = RUNNER.with_suffix(RUNNER.suffix + f".before-ml-first-208-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                shutil.copyfile(RUNNER, backup)
                RUNNER.write_text(text[:idx] + BLOCK + text[idx:], encoding="utf-8")
                result = f"PATCHED 31; backup={backup}"

    lines = [
        "ASTRODDS 208 PATCH MONEYLINE-FIRST BOARD RUNNER",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Result: {result}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
