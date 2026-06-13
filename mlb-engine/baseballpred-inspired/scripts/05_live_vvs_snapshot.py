from pathlib import Path
import csv
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"

ASTRODDS_DIR = ROOT / ".astrodds"
EDGE_DIR = ASTRODDS_DIR / "edge-tracking"
REPORTS = BASE / "reports"

LEDGER = EDGE_DIR / "edge-ledger.json"
SNAPSHOT_CSV = ASTRODDS_DIR / "VVS-live-snapshot-latest.csv"
SNAPSHOT_JSON = ASTRODDS_DIR / "VVS-live-snapshot-latest.json"
REPORT = REPORTS / "05_live_vvs_snapshot_report.txt"

EDGE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def pct_gap(model_probability):
    model = to_float(model_probability)
    if model is None or model <= 0 or model >= 1:
        return None
    return abs((model * 2) - 1) * 100

def edge_pct(row):
    diagnostic = to_float(row.get("diagnosticCalibratedEdgePct"))
    if diagnostic is not None:
        return diagnostic

    model = to_float(row.get("calibratedProbability"))
    market = to_float(row.get("marketProbability"))

    if model is None or market is None:
        return None

    return (model - market) * 100

def edge_bucket(edge):
    if edge is None:
        return "unknown"
    if edge < 5:
        return "3-5%"
    if edge < 10:
        return "5-10%"
    if edge < 15:
        return "10-15%"
    return "15-25%"

def fetch_best_bets():
    with urllib.request.urlopen(API_URL, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))

def is_vvs(row):
    market = to_float(row.get("marketProbability"))
    model = to_float(row.get("calibratedProbability"))
    edge = edge_pct(row)
    gap = pct_gap(model)

    selected = row.get("selectedSide")
    away = row.get("awayTeam")
    home = row.get("homeTeam")

    selected_is_team = selected and (selected == away or selected == home)

    return (
        row.get("status") in ["daily_pick", "buy"]
        and row.get("marketType") == "moneyline"
        and selected_is_team
        and market is not None and 0.30 <= market <= 0.75
        and model is not None
        and edge is not None and 3 <= edge <= 25
        and gap is not None and gap >= 8
        and row.get("matchConfidence") in ["high", "medium"]
        and row.get("riskLevel") not in ["high", "unknown"]
    )

def main():
    snapshot_time = datetime.utcnow().isoformat() + "Z"

    data = fetch_best_bets()
    rows = data.get("bestBetRows", [])

    vvs_rows = []

    for row in rows:
        if not is_vvs(row):
            continue

        market = to_float(row.get("marketProbability"))
        model = to_float(row.get("calibratedProbability"))
        edge = round(edge_pct(row), 2)
        gap = round(pct_gap(model), 2)

        vvs_rows.append({
            "snapshotTime": snapshot_time,
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "awayTeam": row.get("awayTeam"),
            "homeTeam": row.get("homeTeam"),
            "pick": row.get("selectedSide"),
            "status": row.get("status"),
            "marketType": row.get("marketType"),
            "priceSource": row.get("priceSourceUsed"),
            "marketProbability": market,
            "modelProbability": model,
            "edgePct": edge,
            "modelGapPct": gap,
            "edgeBucket": edge_bucket(edge),
            "confidence": row.get("matchConfidence"),
            "risk": row.get("riskLevel"),
            "reason": row.get("mainReason"),
            "result": "pending",
            "paperOnly": True,
        })

    # one pick per game, sorted by strongest edge then model gap
    vvs_rows.sort(key=lambda r: (r["edgePct"], r["modelGapPct"]), reverse=True)

    deduped_game_rows = []
    seen_games = set()

    for row in vvs_rows:
        game_key = f"{row['awayTeam']} @ {row['homeTeam']}"
        if game_key in seen_games:
            continue
        seen_games.add(game_key)
        deduped_game_rows.append(row)

    final_rows = deduped_game_rows[:10]

    # save latest snapshot
    write_json(SNAPSHOT_JSON, final_rows)

    with SNAPSHOT_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "snapshotTime",
            "gameId",
            "date",
            "awayTeam",
            "homeTeam",
            "pick",
            "status",
            "marketType",
            "priceSource",
            "marketProbability",
            "modelProbability",
            "edgePct",
            "modelGapPct",
            "edgeBucket",
            "confidence",
            "risk",
            "reason",
            "result",
            "paperOnly",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)

    # update ledger without duplicates
    existing = read_json(LEDGER)
    combined = existing + final_rows

    deduped = {}
    for row in combined:
        key = f"{row.get('gameId')}|{row.get('pick')}|{row.get('date')}"
        deduped[key] = row

    ledger_rows = list(deduped.values())
    write_json(LEDGER, ledger_rows)

    lines = []
    lines.append("ASTRODDS 05 LIVE VVS SNAPSHOT REPORT")
    lines.append("=" * 42)
    lines.append(f"Snapshot time: {snapshot_time}")
    lines.append(f"API rows: {len(rows)}")
    lines.append(f"VVS rows saved: {len(final_rows)}")
    lines.append(f"Ledger total rows: {len(ledger_rows)}")
    lines.append("")
    lines.append("VVS picks:")

    for row in final_rows:
        lines.append(
            f"- {row['date']} | {row['awayTeam']} @ {row['homeTeam']} | "
            f"Pick: {row['pick']} | Status: {row['status']} | "
            f"Market: {round(row['marketProbability'] * 100, 1)}% | "
            f"Model: {round(row['modelProbability'] * 100, 1)}% | "
            f"Edge: {row['edgePct']}% | Gap: {row['modelGapPct']}% | "
            f"Bucket: {row['edgeBucket']}"
        )

    lines.append("")
    lines.append(f"CSV: {SNAPSHOT_CSV}")
    lines.append(f"JSON: {SNAPSHOT_JSON}")
    lines.append(f"Ledger: {LEDGER}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
