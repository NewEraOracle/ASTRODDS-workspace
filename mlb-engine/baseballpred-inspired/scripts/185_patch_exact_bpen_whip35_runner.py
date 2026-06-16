from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER31 = SCRIPTS / "31_auto_daily_engine_runner.ps1"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "185_patch_exact_bpen_whip35_runner_report.txt"

BLOCK31 = """
Add-Line "Running exact Bpen WHIP35 StatsAPI builder..."
$exactBpen = Join-Path $ScriptDir "183_build_exact_bpen_whip35_from_statsapi.py"
if (Test-Path $exactBpen) {
  $exactBpenProcess = Start-Process python -ArgumentList "`"$exactBpen`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Exact Bpen WHIP35 exit code: $($exactBpenProcess.ExitCode)"
} else {
  Add-Line "Exact Bpen WHIP35 skipped: script not found."
}

Add-Line "Merging exact Bpen WHIP35 into BaseballPred sidecars..."
$mergeBpen = Join-Path $ScriptDir "184_merge_exact_bpen_whip35_into_bbp_sidecars.py"
if (Test-Path $mergeBpen) {
  $mergeBpenProcess = Start-Process python -ArgumentList "`"$mergeBpen`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Merge exact Bpen WHIP35 exit code: $($mergeBpenProcess.ExitCode)"
} else {
  Add-Line "Merge exact Bpen WHIP35 skipped: script not found."
}

"""

BLOCK133 = """
Add-Line "Running exact Bpen WHIP35 StatsAPI builder..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\183_build_exact_bpen_whip35_from_statsapi.py"
Add-Line "183 exact Bpen WHIP35 exit code: $LASTEXITCODE"

Add-Line "Merging exact Bpen WHIP35 into BaseballPred sidecars..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\184_merge_exact_bpen_whip35_into_bbp_sidecars.py"
Add-Line "184 merge exact Bpen WHIP35 exit code: $LASTEXITCODE"

"""

def patch(path, marker, block, needle):
    if not path.exists():
        return f"MISSING {path.name}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        return f"SKIP already patched {path.name}"
    if needle not in text:
        return f"NEEDLE NOT FOUND {path.name}"
    backup = path.with_suffix(path.suffix + f".before-185-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copyfile(path, backup)
    path.write_text(text.replace(needle, block + needle), encoding="utf-8")
    return f"PATCHED {path.name}; backup={backup}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    results = [
        patch(RUNNER31, "Running exact Bpen WHIP35 StatsAPI builder", BLOCK31, 'Add-Line "Running BaseballPred Moneyline readiness audit..."'),
        patch(RUNNER133, "183 exact Bpen WHIP35 exit code", BLOCK133, 'Add-Line "Running full BaseballPred gap report..."'),
    ]

    lines = [
        "ASTRODDS 185 PATCH EXACT BPEN WHIP35 RUNNER",
        "=" * 68,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Results:",
    ] + [f"- {r}" for r in results]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
