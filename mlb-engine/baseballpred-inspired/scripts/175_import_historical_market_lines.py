from pathlib import Path
from datetime import datetime
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
IMPORTS = ASTRO / "imports"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

RAW = IMPORTS / "historical_market_lines_raw.csv"
NORMALIZED = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "175_import_historical_market_lines_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-historical-market-lines-import-latest.json"

FIELDS = ["date","sport","game","market","pick","open_line","close_line","open_price","close_price","final_score","result","source","notes"]

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        return list(csv.DictReader(f))

def pick(row, names):
    low = {k.lower().strip(): k for k in row.keys()}
    for n in names:
        if n.lower() in low:
            return row.get(low[n.lower()], "")
    for k in row.keys():
        lk = k.lower()
        if any(n.lower() in lk for n in names):
            return row.get(k, "")
    return ""

def infer_result(row):
    res = pick(row, ["result", "outcome", "win_loss"])
    if res:
        return str(res).lower()
    return ""

def normalize_row(r):
    home = pick(r, ["home_team", "home"])
    away = pick(r, ["away_team", "away"])
    game = pick(r, ["game", "matchup"])
    if not game and (away or home):
        game = f"{away} @ {home}".strip()

    market = pick(r, ["market", "bet_type", "type"])
    if not market:
        # guess from available columns
        if pick(r, ["total", "over_under", "ou_line"]):
            market = "ou"
        elif pick(r, ["moneyline", "ml", "price"]):
            market = "moneyline"

    return {
        "date": pick(r, ["date", "game_date", "commence_time"])[:10],
        "sport": pick(r, ["sport"]) or "baseball_mlb",
        "game": game,
        "market": market,
        "pick": pick(r, ["pick", "selection", "team", "side"]),
        "open_line": pick(r, ["open_line", "opening_total", "open_total", "total_open"]),
        "close_line": pick(r, ["close_line", "closing_total", "close_total", "total_close", "line"]),
        "open_price": pick(r, ["open_price", "opening_price", "open_odds", "odds_open"]),
        "close_price": pick(r, ["close_price", "closing_price", "close_odds", "odds", "price"]),
        "final_score": pick(r, ["final_score", "score"]),
        "result": infer_result(r),
        "source": pick(r, ["source", "book", "sportsbook"]) or "imported_csv",
        "notes": pick(r, ["notes"]),
    }

def existing_rows():
    if not NORMALIZED.exists():
        return []
    return read_csv(NORMALIZED)

def key(r):
    return "|".join(str(r.get(k,"")).strip().lower() for k in ["date","game","market","pick","close_line","close_price"])

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)
    IMPORTS.mkdir(parents=True, exist_ok=True)

    if not RAW.exists():
        # create empty raw template with common column names
        with RAW.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date","away_team","home_team","market","pick","open_line","close_line","open_price","close_price","final_score","result","source"])
            w.writeheader()

    raw = read_csv(RAW)
    current = existing_rows()
    seen = {key(r) for r in current}
    added = 0

    for r in raw:
        nr = normalize_row(r)
        if not nr["date"] or not nr["game"] or not nr["market"]:
            continue
        k = key(nr)
        if k in seen:
            continue
        current.append(nr)
        seen.add(k)
        added += 1

    with NORMALIZED.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in current:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "rawInput": str(RAW),
        "normalizedOutput": str(NORMALIZED),
        "rawRows": len(raw),
        "addedRows": added,
        "totalNormalizedRows": len(current),
        "status": "READY_FOR_ROI_CLV" if len(current) else "WAITING_FOR_RAW_CSV_ROWS",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 175 IMPORT HISTORICAL MARKET LINES",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Status: {out['status']}",
        f"Raw input: {RAW}",
        f"Normalized output: {NORMALIZED}",
        f"Raw rows: {len(raw)}",
        f"Added rows: {added}",
        f"Total normalized rows: {len(current)}",
        "",
        "Rule:",
        "- Put real odds/closing lines in .astrodds/imports/historical_market_lines_raw.csv",
        "- Then rerun this importer and 171 ROI/CLV.",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
