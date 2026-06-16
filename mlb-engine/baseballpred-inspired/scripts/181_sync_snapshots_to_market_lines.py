from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OPEN_CLOSE = ASTRO / "ASTRODDS-mlb-odds-open-close-from-snapshots.csv"
MARKET_LINES = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "181_sync_snapshots_to_market_lines_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-snapshot-market-line-sync-latest.json"

FIELDS = ["date","sport","game","market","pick","open_line","close_line","open_price","close_price","final_score","result","source","notes"]

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_market(rows):
    with MARKET_LINES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

def key(r):
    return "|".join(str(r.get(k,"")).lower().strip() for k in ["date","game","market","pick","source"])

def market_name(m):
    m = str(m or "").lower()
    if m == "h2h":
        return "moneyline"
    if m == "totals":
        return "ou"
    return m

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    oc_rows = read_csv(OPEN_CLOSE)
    market_rows = read_csv(MARKET_LINES)
    seen = {key(r) for r in market_rows}
    added = 0

    for r in oc_rows:
        m = market_name(r.get("market"))
        nr = {
            "date": r.get("date",""),
            "sport": "baseball_mlb",
            "game": r.get("game",""),
            "market": m,
            "pick": r.get("outcome",""),
            "open_line": r.get("open_point",""),
            "close_line": r.get("close_point",""),
            "open_price": r.get("open_price",""),
            "close_price": r.get("close_price",""),
            "final_score": "",
            "result": "",
            "source": "astrodds_snapshots",
            "notes": f"snapshots={r.get('snapshots','')}; open={r.get('open_snapshot_et','')}; close={r.get('close_snapshot_et','')}",
        }
        k = key(nr)
        if k in seen:
            continue
        market_rows.append(nr)
        seen.add(k)
        added += 1

    write_market(market_rows)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "openCloseRows": len(oc_rows),
        "addedRows": added,
        "marketRowsTotal": len(market_rows),
        "marketLinesCsv": str(MARKET_LINES),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 181 SYNC SNAPSHOTS TO MARKET LINES",
        "=" * 64,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Open/close rows: {len(oc_rows)}",
        f"Added rows: {added}",
        f"Market rows total: {len(market_rows)}",
        f"CSV: {MARKET_LINES}",
        "",
        "Rule:",
        "- Results remain blank until final scores are resolved.",
        "- ROI/CLV becomes meaningful once rows have results and multiple snapshots.",
        f"JSON: {ASTRO / 'ASTRODDS-snapshot-market-line-sync-latest.json'}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
