from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

TEMPLATE = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "170_create_historical_market_lines_template_report.txt"

FIELDS = [
    "date","sport","game","market","pick","open_line","close_line",
    "open_price","close_price","final_score","result","source","notes"
]

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE.exists():
        with TEMPLATE.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()

    lines = [
        "ASTRODDS 170 HISTORICAL MARKET LINES TEMPLATE",
        "=" * 68,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Template created/verified:",
        f"- {TEMPLATE}",
        "",
        "Needed for real ROI/CLV:",
        "- historical Moneyline open/close prices",
        "- historical O/U open/close lines and prices",
        "- final score/result",
        "- source name",
        "",
        "Without this file populated, ROI/CLV stays unavailable.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
