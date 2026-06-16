from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "188_patch_market_line_results_runner_report.txt"

BLOCK = """
Add-Line "Resolving market line results from MLB..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\186_resolve_market_lines_results_from_mlb.py"
Add-Line "186 market line resolve exit code: $LASTEXITCODE"

Add-Line "Running market ROI/CLV summary..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\187_market_roi_clv_summary_report.py"
Add-Line "187 market ROI/CLV summary exit code: $LASTEXITCODE"

Add-Line "Running ROI/CLV backtest from market lines..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\171_roi_clv_backtest_from_market_lines.py"
Add-Line "171 ROI/CLV backtest exit code: $LASTEXITCODE"

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER133.exists():
        result = f"MISSING {RUNNER133}"
    else:
        text = RUNNER133.read_text(encoding="utf-8", errors="ignore")
        if "Resolving market line results from MLB" in text:
            result = "SKIP already patched"
        else:
            needle = 'Add-Line "Running 154 O/U V1/V2 A-B report..."'
            if needle not in text:
                needle = 'Add-Line "ASTRODDS clean daily results runner finished"'
            if needle not in text:
                result = "NEEDLE NOT FOUND"
            else:
                backup = RUNNER133.with_suffix(RUNNER133.suffix + f".before-188-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                shutil.copyfile(RUNNER133, backup)
                RUNNER133.write_text(text.replace(needle, BLOCK + needle), encoding="utf-8")
                result = f"PATCHED 133; backup={backup}"

    lines = [
        "ASTRODDS 188 PATCH MARKET LINE RESULTS RUNNER",
        "=" * 66,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Result:",
        f"- {result}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
