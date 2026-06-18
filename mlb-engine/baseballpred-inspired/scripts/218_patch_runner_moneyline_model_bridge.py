from pathlib import Path
from datetime import datetime
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER = SCRIPTS / "31_auto_daily_engine_runner.ps1"
REPORT = REPORTS / "218_patch_runner_moneyline_model_bridge_report.txt"

CALL_BLOCK = """
Add-Line "Running Moneyline model bridge pipeline 217..."
$moneylineBridgePipeline = Join-Path $ScriptDir "217_run_moneyline_model_bridge_pipeline.ps1"
if (Test-Path $moneylineBridgePipeline) {
  $p = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$moneylineBridgePipeline`" -Workspace `"$Workspace`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline model bridge pipeline 217 exit code: $($p.ExitCode)"
} else {
  Add-Line "Moneyline model bridge pipeline 217 skipped: script not found."
}

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER.exists():
        result = f"MISSING {RUNNER}"
    else:
        text = RUNNER.read_text(encoding="utf-8", errors="ignore")
        backup = RUNNER.with_suffix(RUNNER.suffix + f".before-model-bridge-218-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copyfile(RUNNER, backup)

        # Remove older moneyline-only 214 call.
        text = re.sub(r'Add-Line "Running Moneyline-only board pipeline 214\.\.\."[\s\S]*?Add-Line "Moneyline-only board pipeline 214 skipped: script not found\."\s*\}\s*', "", text)

        marker = 'Add-Line "Running Telegram result tracking..."'
        idx = text.find(marker)
        if idx == -1:
            result = "ERROR: Telegram tracking marker not found"
        elif "Running Moneyline model bridge pipeline 217" in text:
            result = "SKIP already patched"
        else:
            text = text[:idx] + CALL_BLOCK + text[idx:]
            RUNNER.write_text(text, encoding="utf-8")
            result = f"PATCHED runner with 217 model bridge before Telegram tracking; backup={backup}"

    lines = [
        "ASTRODDS 218 PATCH RUNNER MONEYLINE MODEL BRIDGE",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Result: {result}",
        "",
        "Expected after next runner:",
        "- Running Moneyline model bridge pipeline 217...",
        "- Moneyline model bridge pipeline 217 exit code: 0",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
