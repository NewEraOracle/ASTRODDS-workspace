from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER31 = SCRIPTS / "31_auto_daily_engine_runner.ps1"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "173_patch_baseballpred_moneyline_sidecars_report.txt"

BLOCK31 = """
Add-Line "Running BaseballPred Moneyline readiness audit..."
$bbpMlReady = Join-Path $ScriptDir "167_baseballpred_moneyline_readiness_audit.py"
if (Test-Path $bbpMlReady) {
  $bbpMlReadyProcess = Start-Process python -ArgumentList "`"$bbpMlReady`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "BaseballPred Moneyline readiness exit code: $($bbpMlReadyProcess.ExitCode)"
}

Add-Line "Running BaseballPred feature bridge..."
$bbpBridge = Join-Path $ScriptDir "168_build_baseballpred_feature_bridge.py"
if (Test-Path $bbpBridge) {
  $bbpBridgeProcess = Start-Process python -ArgumentList "`"$bbpBridge`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "BaseballPred feature bridge exit code: $($bbpBridgeProcess.ExitCode)"
}

Add-Line "Running Moneyline BaseballPred sidecar..."
$bbpMl = Join-Path $ScriptDir "169_moneyline_baseballpred_sidecar_audit.py"
if (Test-Path $bbpMl) {
  $bbpMlProcess = Start-Process python -ArgumentList "`"$bbpMl`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Moneyline BaseballPred sidecar exit code: $($bbpMlProcess.ExitCode)"
}

"""

BLOCK133 = """
Add-Line "Running BaseballPred ROI/CLV backtest..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\171_roi_clv_backtest_from_market_lines.py"
Add-Line "171 ROI/CLV backtest exit code: $LASTEXITCODE"

Add-Line "Running full BaseballPred gap report..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\172_full_baseballpred_gap_report.py"
Add-Line "172 gap report exit code: $LASTEXITCODE"

"""

def patch(path, marker, block, needle):
    if not path.exists():
        return f"MISSING {path.name}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        return f"SKIP already patched {path.name}"
    if needle not in text:
        return f"NEEDLE NOT FOUND {path.name}"
    backup = path.with_suffix(path.suffix + f".before-173-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copyfile(path, backup)
    path.write_text(text.replace(needle, block + needle), encoding="utf-8")
    return f"PATCHED {path.name}; backup={backup}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = [
        patch(RUNNER31, "Running Moneyline BaseballPred sidecar", BLOCK31, 'Add-Line "Running Telegram result tracking..."'),
        patch(RUNNER133, "Running full BaseballPred gap report", BLOCK133, 'Add-Line "ASTRODDS clean daily results runner finished"'),
    ]
    lines = ["ASTRODDS 173 PATCH BASEBALLPRED MONEYLINE SIDECARS","="*72,f"Generated UTC: {datetime.utcnow().isoformat()}Z","", "Results:"] + [f"- {r}" for r in results]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
