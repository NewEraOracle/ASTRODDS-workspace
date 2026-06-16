from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER31 = SCRIPTS / "31_auto_daily_engine_runner.ps1"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "182_patch_odds_collector_runner_report.txt"

BLOCK31 = """
Add-Line "Running credit-safe MLB odds collector..."
$oddsCollector = Join-Path $ScriptDir "179_credit_safe_mlb_odds_collector.py"
if (Test-Path $oddsCollector) {
  $oddsCollectorProcess = Start-Process python -ArgumentList "`"$oddsCollector`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "MLB odds collector exit code: $($oddsCollectorProcess.ExitCode)"
} else {
  Add-Line "MLB odds collector skipped: script not found."
}

Add-Line "Building odds open/close from snapshots..."
$oddsOpenClose = Join-Path $ScriptDir "180_build_odds_open_close_from_snapshots.py"
if (Test-Path $oddsOpenClose) {
  $oddsOpenCloseProcess = Start-Process python -ArgumentList "`"$oddsOpenClose`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Odds open/close builder exit code: $($oddsOpenCloseProcess.ExitCode)"
} else {
  Add-Line "Odds open/close builder skipped: script not found."
}

Add-Line "Syncing snapshots to market lines..."
$oddsMarketSync = Join-Path $ScriptDir "181_sync_snapshots_to_market_lines.py"
if (Test-Path $oddsMarketSync) {
  $oddsMarketSyncProcess = Start-Process python -ArgumentList "`"$oddsMarketSync`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Snapshot market line sync exit code: $($oddsMarketSyncProcess.ExitCode)"
} else {
  Add-Line "Snapshot market line sync skipped: script not found."
}

"""

BLOCK133 = """
Add-Line "Building odds open/close from snapshots..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\180_build_odds_open_close_from_snapshots.py"
Add-Line "180 odds open/close exit code: $LASTEXITCODE"

Add-Line "Syncing snapshots to market lines..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\181_sync_snapshots_to_market_lines.py"
Add-Line "181 snapshot market sync exit code: $LASTEXITCODE"

"""

def patch(path, marker, block, needle):
    if not path.exists():
        return f"MISSING {path.name}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        return f"SKIP already patched {path.name}"
    if needle not in text:
        return f"NEEDLE NOT FOUND {path.name}"
    backup = path.with_suffix(path.suffix + f".before-182-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copyfile(path, backup)
    path.write_text(text.replace(needle, block + needle), encoding="utf-8")
    return f"PATCHED {path.name}; backup={backup}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = [
        patch(RUNNER31, "Running credit-safe MLB odds collector", BLOCK31, 'Add-Line "Running credit guard..."'),
        patch(RUNNER133, "Syncing snapshots to market lines", BLOCK133, 'Add-Line "ASTRODDS clean daily results runner finished"'),
    ]
    lines = ["ASTRODDS 182 PATCH ODDS COLLECTOR RUNNER","="*64,f"Generated UTC: {datetime.utcnow().isoformat()}Z","","Results:"] + [f"- {r}" for r in results]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
