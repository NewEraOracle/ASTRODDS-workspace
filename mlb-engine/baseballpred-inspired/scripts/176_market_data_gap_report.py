from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
LINES = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "176_market_data_gap_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-market-data-gap-latest.json"

def read_rows():
    if not LINES.exists():
        return []
    with LINES.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = [r for r in read_rows() if r.get("date")]
    ml = [r for r in rows if "money" in str(r.get("market","")).lower() or str(r.get("market","")).lower() == "ml"]
    ou = [r for r in rows if str(r.get("market","")).lower() in ("ou", "total", "over_under") or "total" in str(r.get("market","")).lower()]
    have_closing = [r for r in rows if r.get("close_price") or r.get("close_line")]
    resolved = [r for r in rows if str(r.get("result","")).lower() in ("win","loss","push")]

    gaps = []
    if not ml:
        gaps.append("historical_moneyline_odds")
    if not ou:
        gaps.append("historical_ou_closing_lines")
    if len(resolved) < 50:
        gaps.append("real ROI/CLV backtest rows")

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "rows": len(rows),
        "moneylineRows": len(ml),
        "ouRows": len(ou),
        "rowsWithClosingData": len(have_closing),
        "resolvedRows": len(resolved),
        "remainingGaps": gaps,
        "status": "MARKET_DATA_READY" if not gaps else "MARKET_DATA_INCOMPLETE",
        "input": str(LINES),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 176 MARKET DATA GAP REPORT",
        "=" * 60,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Status: {out['status']}",
        f"Rows: {out['rows']}",
        f"Moneyline rows: {out['moneylineRows']}",
        f"O/U rows: {out['ouRows']}",
        f"Rows with closing data: {out['rowsWithClosingData']}",
        f"Resolved rows: {out['resolvedRows']}",
        "",
        "Remaining gaps:",
    ]
    lines += [f"- {g}" for g in gaps] if gaps else ["- none"]
    lines += ["", f"Input: {LINES}", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
