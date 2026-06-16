from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER31 = SCRIPTS / "31_auto_daily_engine_runner.ps1"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "161_patch_sidecar_pipeline_runner_report.txt"

BLOCK31 = """
Add-Line "Running O/U V2 sidecar context enrichment..."
$ouV2Context = Join-Path $ScriptDir "151_ou_live_context_enrichment_audit.py"
if (Test-Path $ouV2Context) {
  $ouV2ContextProcess = Start-Process python -ArgumentList "`"$ouV2Context`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U V2 context enrichment exit code: $($ouV2ContextProcess.ExitCode)"
} else {
  Add-Line "O/U V2 context enrichment skipped: script not found."
}

Add-Line "Running O/U V2 strict paper score..."
$ouV2Strict = Join-Path $ScriptDir "152_ou_v2_strict_paper_score_audit.py"
if (Test-Path $ouV2Strict) {
  $ouV2StrictProcess = Start-Process python -ArgumentList "`"$ouV2Strict`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U V2 strict paper score exit code: $($ouV2StrictProcess.ExitCode)"
} else {
  Add-Line "O/U V2 strict paper score skipped: script not found."
}

Add-Line "Running O/U V2 batting context merge..."
$ouV2Batting = Join-Path $ScriptDir "159_merge_lineup_obp_slg_proxy_into_ou_v2.py"
if (Test-Path $ouV2Batting) {
  $ouV2BattingProcess = Start-Process python -ArgumentList "`"$ouV2Batting`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U V2 batting context merge exit code: $($ouV2BattingProcess.ExitCode)"
} else {
  Add-Line "O/U V2 batting context merge skipped: script not found."
}

Add-Line "Running O/U V2 batting context score..."
$ouV2BattingScore = Join-Path $ScriptDir "160_ou_v2_batting_context_score_audit.py"
if (Test-Path $ouV2BattingScore) {
  $ouV2BattingScoreProcess = Start-Process python -ArgumentList "`"$ouV2BattingScore`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U V2 batting context score exit code: $($ouV2BattingScoreProcess.ExitCode)"
} else {
  Add-Line "O/U V2 batting context score skipped: script not found."
}

Add-Line "Running O/U V1/V2 A-B tracker..."
$ouABTracker = Join-Path $ScriptDir "153_ou_v1_v2_ab_test_tracker.py"
if (Test-Path $ouABTracker) {
  $ouABProcess = Start-Process python -ArgumentList "`"$ouABTracker`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U V1/V2 A-B tracker exit code: $($ouABProcess.ExitCode)"
} else {
  Add-Line "O/U V1/V2 A-B tracker skipped: script not found."
}

Add-Line "Running ASTRODDS today control board..."
$todayBoard = Join-Path $ScriptDir "155_astrodds_today_control_board.py"
if (Test-Path $todayBoard) {
  $todayBoardProcess = Start-Process python -ArgumentList "`"$todayBoard`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Today control board exit code: $($todayBoardProcess.ExitCode)"
} else {
  Add-Line "Today control board skipped: script not found."
}

"""

BLOCK133 = """
Add-Line "Running 154 O/U V1/V2 A-B report..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\154_ou_v1_v2_ab_test_report.py"
Add-Line "154 O/U A-B report exit code: $LASTEXITCODE"

Add-Line "Running 158 postponed/suspended safety audit..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\158_postponed_suspended_safety_audit.py"
Add-Line "158 postponed/suspended safety exit code: $LASTEXITCODE"

"""

def patch_file(path, marker, block, needle):
    if not path.exists():
        return f"missing {path}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        return f"already patched {path.name}"
    if needle not in text:
        return f"needle not found in {path.name}: {needle}"
    backup = path.with_suffix(path.suffix + f".before-161-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copyfile(path, backup)
    text = text.replace(needle, block + needle)
    path.write_text(text, encoding="utf-8")
    return f"patched {path.name}; backup={backup}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = [
        patch_file(RUNNER31, "Running O/U V2 batting context score", BLOCK31, 'Add-Line "Running Telegram result tracking..."'),
        patch_file(RUNNER133, "Running 154 O/U V1/V2 A-B report", BLOCK133, 'Add-Line "ASTRODDS clean daily results runner finished"')
    ]
    lines = [
        "ASTRODDS 161 PATCH SIDECAR PIPELINE RUNNER",
        "=" * 64,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Rules:",
        "- Safe runner patch.",
        "- Does not replace live Telegram senders.",
        "- Adds sidecar audits after O/U JSON exists and before result reports.",
        "",
        "Results:",
    ] + [f"- {r}" for r in results]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
