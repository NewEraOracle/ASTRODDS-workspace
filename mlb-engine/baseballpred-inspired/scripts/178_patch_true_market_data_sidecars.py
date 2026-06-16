from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
RUNNER133 = SCRIPTS / "133_clean_daily_results_runner.ps1"
REPORT = REPORTS / "178_patch_true_market_data_sidecars_report.txt"

BLOCK = """
Add-Line "Running 174 exact Bpen WHIP35 audit..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\174_build_exact_bpen_whip35_audit.py"
Add-Line "174 Bpen WHIP35 exit code: $LASTEXITCODE"

Add-Line "Running 175 historical market line importer..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\175_import_historical_market_lines.py"
Add-Line "175 market importer exit code: $LASTEXITCODE"

Add-Line "Running 176 market data gap report..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\176_market_data_gap_report.py"
Add-Line "176 market gap exit code: $LASTEXITCODE"

Add-Line "Running 177 true feature final gap report..."
python ".\\mlb-engine\\baseballpred-inspired\\scripts\\177_true_feature_final_gap_report.py"
Add-Line "177 true feature gap exit code: $LASTEXITCODE"

"""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not RUNNER133.exists():
        result = f"MISSING {RUNNER133}"
    else:
        text = RUNNER133.read_text(encoding="utf-8", errors="ignore")
        if "Running 177 true feature final gap report" in text:
            result = "SKIP already patched"
        else:
            needle = 'Add-Line "ASTRODDS clean daily results runner finished"'
            if needle not in text:
                result = "NEEDLE NOT FOUND"
            else:
                backup = RUNNER133.with_suffix(RUNNER133.suffix + f".before-178-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
                shutil.copyfile(RUNNER133, backup)
                RUNNER133.write_text(text.replace(needle, BLOCK + needle), encoding="utf-8")
                result = f"PATCHED 133; backup={backup}"

    lines = ["ASTRODDS 178 PATCH TRUE MARKET DATA SIDECARS","="*66,f"Generated UTC: {datetime.utcnow().isoformat()}Z","", "Result:", f"- {result}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
