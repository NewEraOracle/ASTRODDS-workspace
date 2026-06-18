from pathlib import Path
from datetime import datetime
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER = SCRIPTS / "31_auto_daily_engine_runner.ps1"
REPORT = REPORTS / "224_patch_runner_moneyline_production_board_report.txt"

CALL_BLOCK = """
Add-Line "Running Moneyline production board pipeline 223..."
$moneylineProductionPipeline = Join-Path $ScriptDir "223_run_moneyline_production_board_pipeline.ps1"
if (Test-Path $moneylineProductionPipeline) {
  $p = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$moneylineProductionPipeline`" -Workspace `"$Workspace`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline production board pipeline 223 exit code: $($p.ExitCode)"
} else {
  Add-Line "Moneyline production board pipeline 223 skipped: script not found."
}

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    if not RUNNER.exists():
        result = f"MISSING {RUNNER}"
    else:
        text = RUNNER.read_text(encoding="utf-8", errors="ignore")
        backup = RUNNER.with_suffix(RUNNER.suffix + f".before-production-board-224-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copyfile(RUNNER, backup)

        # Remove older moneyline-only/model/current calls.
        patterns = [
            r'Add-Line "Running Moneyline-only board pipeline 214\.\.\."[\s\S]*?Add-Line "Moneyline-only board pipeline 214 skipped: script not found\."\s*\}\s*',
            r'Add-Line "Running Moneyline model bridge pipeline 217\.\.\."[\s\S]*?Add-Line "Moneyline model bridge pipeline 217 skipped: script not found\."\s*\}\s*',
            r'Add-Line "Running Moneyline current edge pipeline 220\.\.\."[\s\S]*?Add-Line "Moneyline current edge pipeline 220 skipped: script not found\."\s*\}\s*',
            r'Add-Line "Running full board pipeline 212\.\.\."[\s\S]*?Add-Line "Full board pipeline 212 skipped: script not found\."\s*\}\s*',
        ]
        for pat in patterns:
            text = re.sub(pat, "", text)

        marker = 'Add-Line "Running Telegram result tracking..."'
        idx = text.find(marker)
        if idx == -1:
            result = "ERROR: Telegram tracking marker not found"
        elif "Running Moneyline production board pipeline 223" in text:
            result = "SKIP already patched"
        else:
            text = text[:idx] + CALL_BLOCK + text[idx:]
            RUNNER.write_text(text, encoding="utf-8")
            result = f"PATCHED runner with 223 production board before Telegram tracking; backup={backup}"

    lines = [
        "ASTRODDS 224 PATCH RUNNER MONEYLINE PRODUCTION BOARD",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Result: {result}",
        "",
        "Expected after next runner:",
        "- Running Moneyline production board pipeline 223...",
        "- Moneyline production board pipeline 223 exit code: 0",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
