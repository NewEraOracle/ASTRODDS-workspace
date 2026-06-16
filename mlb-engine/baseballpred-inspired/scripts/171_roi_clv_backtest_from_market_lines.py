from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

TEMPLATE = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
OUT_JSON = ASTRO / "ASTRODDS-roi-clv-backtest-latest.json"
REPORT = REPORTS / "171_roi_clv_backtest_from_market_lines_report.txt"

def read_rows():
    if not TEMPLATE.exists():
        return []
    with TEMPLATE.open("r", encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("date") and r.get("market")]

def american_profit(price, stake=1.0):
    try:
        p = float(price)
    except Exception:
        return None
    if p > 0:
        return stake * p / 100.0
    return stake * 100.0 / abs(p)

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = read_rows()
    wins = losses = pushes = 0
    profit = 0.0
    clv_rows = []

    for r in rows:
        res = str(r.get("result","")).lower()
        price = r.get("close_price") or r.get("open_price")
        if res == "win":
            wins += 1
            prof = american_profit(price)
            profit += prof if prof is not None else 1.0
        elif res == "loss":
            losses += 1
            profit -= 1.0
        elif res == "push":
            pushes += 1

        try:
            open_line = float(r.get("open_line") or 0)
            close_line = float(r.get("close_line") or 0)
            clv_rows.append(close_line - open_line)
        except Exception:
            pass

    resolved = wins + losses
    roi = (profit / resolved * 100.0) if resolved else 0.0
    avg_clv = sum(clv_rows) / len(clv_rows) if clv_rows else 0.0

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "rows": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "profitUnits": round(profit, 4),
        "roiPct": round(roi, 2),
        "avgClvLineMove": round(avg_clv, 4),
        "status": "READY" if rows else "WAITING_FOR_HISTORICAL_MARKET_LINES",
        "input": str(TEMPLATE),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 171 ROI/CLV BACKTEST FROM MARKET LINES",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Status: {out['status']}",
        f"Rows: {out['rows']}",
        f"Record: {wins}-{losses}, Push={pushes}",
        f"Profit units: {out['profitUnits']}",
        f"ROI: {out['roiPct']}%",
        f"Avg CLV line move: {out['avgClvLineMove']}",
        "",
        f"Input: {TEMPLATE}",
        "",
        "Decision:",
        "- If status is WAITING, add real historical market lines to template.",
        "- Do not claim ROI/CLV edge until this report has real rows.",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
