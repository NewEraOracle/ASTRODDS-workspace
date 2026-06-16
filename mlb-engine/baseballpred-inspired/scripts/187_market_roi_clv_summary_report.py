from pathlib import Path
from datetime import datetime
import csv
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

MARKET_CSV = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "187_market_roi_clv_summary_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-market-roi-clv-summary-latest.json"

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def fnum(v, default=None):
    try:
        s = str(v).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def american_profit(price, stake=1.0):
    p = fnum(price, None)
    if p is None:
        return 1.0
    if p > 0:
        return stake * p / 100.0
    return stake * 100.0 / abs(p)

def summarize(rows):
    wins = losses = pushes = 0
    profit = 0.0
    clv_vals = []
    resolved = []
    pending = 0

    for r in rows:
        res = str(r.get("result","")).lower()
        if res not in ("win", "loss", "push"):
            pending += 1
            continue
        resolved.append(r)
        if res == "win":
            wins += 1
            profit += american_profit(r.get("close_price") or r.get("open_price"))
        elif res == "loss":
            losses += 1
            profit -= 1.0
        else:
            pushes += 1

        open_line = fnum(r.get("open_line"), None)
        close_line = fnum(r.get("close_line"), None)
        if open_line is not None and close_line is not None:
            clv_vals.append(close_line - open_line)

    wp_denom = wins + losses
    return {
        "rows": len(rows),
        "resolvedRows": len(resolved),
        "pendingRows": pending,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "winRate": round(100*wins/wp_denom, 1) if wp_denom else 0.0,
        "profitUnits": round(profit, 4),
        "roiPct": round(100*profit/wp_denom, 2) if wp_denom else 0.0,
        "avgClvLineMove": round(sum(clv_vals)/len(clv_vals), 4) if clv_vals else 0.0,
    }

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = read_csv(MARKET_CSV)
    groups = defaultdict(list)
    for r in rows:
        groups[str(r.get("market","")).lower()].append(r)

    summary_all = summarize(rows)
    by_market = {m: summarize(rs) for m, rs in groups.items()}

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "all": summary_all,
        "byMarket": by_market,
        "csv": str(MARKET_CSV),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 187 MARKET ROI/CLV SUMMARY REPORT",
        "=" * 66,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "All:",
        f"- Rows: {summary_all['rows']}",
        f"- Resolved: {summary_all['resolvedRows']}",
        f"- Pending: {summary_all['pendingRows']}",
        f"- Record: {summary_all['wins']}-{summary_all['losses']}, Push={summary_all['pushes']}",
        f"- Win rate: {summary_all['winRate']}%",
        f"- Profit units: {summary_all['profitUnits']}",
        f"- ROI: {summary_all['roiPct']}%",
        f"- Avg CLV line move: {summary_all['avgClvLineMove']}",
        "",
        "By market:",
    ]
    for m, s in by_market.items():
        lines.append(
            f"- {m}: rows={s['rows']} resolved={s['resolvedRows']} pending={s['pendingRows']} "
            f"record={s['wins']}-{s['losses']} push={s['pushes']} ROI={s['roiPct']}%"
        )
    lines += ["", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
