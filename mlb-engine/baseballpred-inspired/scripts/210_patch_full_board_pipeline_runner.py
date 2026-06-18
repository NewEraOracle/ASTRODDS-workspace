from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER = SCRIPTS / "31_auto_daily_engine_runner.ps1"
REPORT = REPORTS / "210_patch_full_board_pipeline_runner_report.txt"

FULL_BLOCK = r"""
Add-Line "Running O/U batting match audit..."
$ouBattingMatch = Join-Path $ScriptDir "199_fix_ou_batting_game_match_audit.py"
if (Test-Path $ouBattingMatch) {
  $ouBattingMatchProcess = Start-Process python -ArgumentList "`"$ouBattingMatch`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U batting match audit exit code: $($ouBattingMatchProcess.ExitCode)"
} else { Add-Line "O/U batting match audit skipped: script not found." }

Add-Line "Running BaseballPred full slate ranker..."
$fullSlateRanker = Join-Path $ScriptDir "198_baseballpred_full_slate_ranker.py"
if (Test-Path $fullSlateRanker) {
  $fullSlateRankerProcess = Start-Process python -ArgumentList "`"$fullSlateRanker`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "BaseballPred full slate ranker exit code: $($fullSlateRankerProcess.ExitCode)"
} else { Add-Line "BaseballPred full slate ranker skipped: script not found." }

Add-Line "Running full slate game board report..."
$gameBoardReport = Join-Path $ScriptDir "200_astrodds_full_slate_game_board_report.py"
if (Test-Path $gameBoardReport) {
  $gameBoardReportProcess = Start-Process python -ArgumentList "`"$gameBoardReport`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Full slate game board report exit code: $($gameBoardReportProcess.ExitCode)"
} else { Add-Line "Full slate game board report skipped: script not found." }

Add-Line "Running expanded Moneyline full slate board..."
$expandMoneylineBoard = Join-Path $ScriptDir "202_expand_moneyline_full_slate_board.py"
if (Test-Path $expandMoneylineBoard) {
  $expandMoneylineBoardProcess = Start-Process python -ArgumentList "`"$expandMoneylineBoard`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Expanded Moneyline full slate board exit code: $($expandMoneylineBoardProcess.ExitCode)"
} else { Add-Line "Expanded Moneyline full slate board skipped: script not found." }

Add-Line "Running dedupe full slate game board..."
$dedupeGameBoard = Join-Path $ScriptDir "203_dedupe_full_slate_game_board.py"
if (Test-Path $dedupeGameBoard) {
  $dedupeGameBoardProcess = Start-Process python -ArgumentList "`"$dedupeGameBoard`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Dedupe full slate game board exit code: $($dedupeGameBoardProcess.ExitCode)"
} else { Add-Line "Dedupe full slate game board skipped: script not found." }

Add-Line "Running fixed Moneyline BaseballPred full slate board..."
$mlFullSlateFixed = Join-Path $ScriptDir "206_moneyline_baseballpred_full_slate_fixed.py"
if (Test-Path $mlFullSlateFixed) {
  $mlFullSlateFixedProcess = Start-Process python -ArgumentList "`"$mlFullSlateFixed`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Fixed Moneyline full slate board exit code: $($mlFullSlateFixedProcess.ExitCode)"
} else { Add-Line "Fixed Moneyline full slate board skipped: script not found." }

Add-Line "Running Moneyline-first full slate board report..."
$mlFirstBoardReport = Join-Path $ScriptDir "207_full_slate_game_board_moneyline_first_report.py"
if (Test-Path $mlFirstBoardReport) {
  $mlFirstBoardReportProcess = Start-Process python -ArgumentList "`"$mlFirstBoardReport`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline-first board report exit code: $($mlFirstBoardReportProcess.ExitCode)"
} else { Add-Line "Moneyline-first board report skipped: script not found." }

"""

def cleanup(text):
    markers = [
        'Add-Line "Running O/U batting match audit..."',
        'Add-Line "Running BaseballPred full slate ranker..."',
        'Add-Line "Running full slate game board report..."',
        'Add-Line "Running expanded Moneyline full slate board..."',
        'Add-Line "Running dedupe full slate game board..."',
        'Add-Line "Running fixed Moneyline BaseballPred full slate board..."',
        'Add-Line "Running Moneyline-first full slate board report..."',
    ]
    positions = [text.find(m) for m in markers if text.find(m) != -1]
    if not positions:
        return text
    start = min(positions)
    end = text.find("Running Telegram result tracking", start)
    if end == -1:
        return text
    return text[:start] + text[end:]

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER.exists():
        result = f"MISSING {RUNNER}"
    else:
        text = RUNNER.read_text(encoding="utf-8", errors="ignore")
        backup = RUNNER.with_suffix(RUNNER.suffix + f".before-full-board-210-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copyfile(RUNNER, backup)
        text = cleanup(text)
        idx = text.find("Running Telegram result tracking")
        if idx == -1:
            result = "NEEDLE NOT FOUND"
        else:
            RUNNER.write_text(text[:idx] + FULL_BLOCK + text[idx:], encoding="utf-8")
            result = f"PATCHED full board pipeline before Telegram result tracking; backup={backup}"
    lines = [
        "ASTRODDS 210 PATCH FULL BOARD PIPELINE RUNNER",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Result: {result}",
        "",
        "Required order after every scan:",
        "- 199 -> 198 -> 200 -> 202 -> 203 -> 206 -> 207",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
