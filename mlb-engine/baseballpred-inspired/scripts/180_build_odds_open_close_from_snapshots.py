from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

LEDGER = ASTRO / "ASTRODDS-mlb-odds-snapshot-ledger.csv"
OUT_CSV = ASTRO / "ASTRODDS-mlb-odds-open-close-from-snapshots.csv"
OUT_JSON = ASTRO / "ASTRODDS-mlb-odds-open-close-latest.json"
REPORT = REPORTS / "180_build_odds_open_close_from_snapshots_report.txt"

ET = ZoneInfo("America/New_York")

FIELDS = [
    "date","game_id","game","market","outcome","bookmaker",
    "open_snapshot_et","open_price","open_point",
    "close_snapshot_et","close_price","close_point",
    "snapshots","source"
]

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

def key(r):
    game = f"{r.get('away_team','')} @ {r.get('home_team','')}"
    return "|".join([
        str(r.get("game_id","")),
        game,
        str(r.get("market","")),
        str(r.get("outcome","")),
        str(r.get("bookmaker","")),
    ])

def game_date(r):
    ct = str(r.get("commence_time",""))
    return ct[:10] if len(ct) >= 10 else str(r.get("snapshot_et",""))[:10]

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = read_csv(LEDGER)
    grouped = {}

    for r in rows:
        k = key(r)
        grouped.setdefault(k, []).append(r)

    out_rows = []
    for k, items in grouped.items():
        items = sorted(items, key=lambda x: str(x.get("snapshot_et","")))
        first, last = items[0], items[-1]
        game = f"{first.get('away_team','')} @ {first.get('home_team','')}"
        out_rows.append({
            "date": game_date(first),
            "game_id": first.get("game_id",""),
            "game": game,
            "market": first.get("market",""),
            "outcome": first.get("outcome",""),
            "bookmaker": first.get("bookmaker",""),
            "open_snapshot_et": first.get("snapshot_et",""),
            "open_price": first.get("price",""),
            "open_point": first.get("point",""),
            "close_snapshot_et": last.get("snapshot_et",""),
            "close_price": last.get("price",""),
            "close_point": last.get("point",""),
            "snapshots": len(items),
            "source": "astrodds_snapshots",
        })

    write_csv(OUT_CSV, out_rows)
    save = {
        "generatedAt": datetime.now(ET).isoformat(),
        "inputRows": len(rows),
        "outputRows": len(out_rows),
        "csv": str(OUT_CSV),
        "note": "Open/close are first/last snapshots captured by ASTRODDS, not full historical bookmaker close unless captured near game start.",
    }
    OUT_JSON.write_text(json.dumps(save, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 180 BUILD ODDS OPEN/CLOSE FROM SNAPSHOTS",
        "=" * 72,
        f"Generated ET: {save['generatedAt']}",
        "",
        f"Input rows: {len(rows)}",
        f"Output rows: {len(out_rows)}",
        f"CSV: {OUT_CSV}",
        "",
        "Rule:",
        "- Open = first ASTRODDS snapshot.",
        "- Close = latest ASTRODDS snapshot.",
        "- This becomes better as scans run 9:30 / 14:00 / 17:10.",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
