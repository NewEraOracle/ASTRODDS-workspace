from pathlib import Path
from datetime import datetime
import shutil
ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "166_patch_nightly_full_build_validation_report.txt"
BLOCK = """
Add-Line "Running 164 full build validation..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\164_full_build_validation_report.py"
Add-Line "164 full build validation exit code: $LASTEXITCODE"

Add-Line "Running 165 tomorrow review commands..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\165_tomorrow_review_commands.py"
Add-Line "165 tomorrow review commands exit code: $LASTEXITCODE"

"""
def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER133.exists():
        result = f"MISSING {RUNNER133}"
    else:
        text = RUNNER133.read_text(encoding="utf-8", errors="ignore")
        if "Running 164 full build validation" in text:
            result = "SKIP already patched"
        else:
            needle = 'Add-Line "ASTRODDS clean daily results runner finished"'
            if needle not in text:
                result = "NEEDLE NOT FOUND"
            else:
                backup = RUNNER133.with_suffix(RUNNER133.suffix + f".before-166-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                shutil.copyfile(RUNNER133, backup)
                RUNNER133.write_text(text.replace(needle, BLOCK + needle), encoding="utf-8")
                result = f"PATCHED 133; backup={backup}"
    lines = ["ASTRODDS 166 PATCH NIGHTLY FULL BUILD VALIDATION","="*70,f"Generated UTC: {datetime.utcnow().isoformat()}Z","","Result:",f"- {result}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
