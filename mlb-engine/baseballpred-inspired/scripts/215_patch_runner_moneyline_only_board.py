from pathlib import Path
from datetime import datetime
import re, shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER = SCRIPTS / "31_auto_daily_engine_runner.ps1"
REPORT = REPORTS / "215_patch_runner_moneyline_only_board_report.txt"

CALL_BLOCK = """
Add-Line "Running Moneyline-only board pipeline 214..."
$moneylineOnlyPipeline = Join-Path $ScriptDir "214_run_moneyline_only_board_pipeline.ps1"
if (Test-Path $moneylineOnlyPipeline) {
  $p = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$moneylineOnlyPipeline`" -Workspace `"$Workspace`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline-only board pipeline 214 exit code: $($p.ExitCode)"
} else {
  Add-Line "Moneyline-only board pipeline 214 skipped: script not found."
}

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER.exists():
        result = f"MISSING {RUNNER}"
    else:
        text = RUNNER.read_text(encoding="utf-8", errors="ignore")
        backup = RUNNER.with_suffix(RUNNER.suffix + f".before-moneyline-only-215-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copyfile(RUNNER, backup)

        text = re.sub(r'Add-Line "Running full board pipeline 212\.\.\."[\s\S]*?Add-Line "Full board pipeline 212 skipped: script not found\."\s*\}\s*', "", text)

        marker = 'Add-Line "Running Telegram result tracking..."'
        idx = text.find(marker)
        if idx == -1:
            result = "ERROR: Telegram tracking marker not found"
        elif "Running Moneyline-only board pipeline 214" in text:
            result = "SKIP already patched"
        else:
            text = text[:idx] + CALL_BLOCK + text[idx:]
            RUNNER.write_text(text, encoding="utf-8")
            result = f"PATCHED runner with Moneyline-only board call before Telegram result tracking; backup={backup}"

    lines = [
        "ASTRODDS 215 PATCH RUNNER MONEYLINE ONLY BOARD",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Result: {result}",
        "",
        "Expected after next runner:",
        "- Running Moneyline-only board pipeline 214...",
        "- Moneyline-only board pipeline 214 exit code: 0",
        "- No O/U board pipeline required for moneyline display.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
