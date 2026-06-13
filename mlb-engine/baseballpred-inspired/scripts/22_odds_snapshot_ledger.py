from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

INPUT = WORKSPACE / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
LEDGER_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.json"
LEDGER_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.csv"
REPORT = ROOT / "reports" / "22_odds_snapshot_ledger_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def snapshot_row(row, snapshot_at):
    market = fnum(row.get("marketProbability"))
    raw = fnum(row.get("rawModelProbability"))
    cal = fnum(row.get("calibratedProbabilityV2"))

    return {
        "snapshotAt": snapshot_at,
        "gameId": row.get("gameId"),
        "gamePk": row.get("gamePk"),
        "date": row.get("date"),
        "game": row.get("game"),
        "awayTeam": row.get("awayTeam"),
        "homeTeam": row.get("homeTeam"),
        "pick": row.get("pick"),
        "marketProbability": market,
        "rawModelProbability": raw,
        "calibratedProbabilityV2": cal,
        "rawEdgePct": row.get("rawEdgePct"),
        "calibratedEdgePct": row.get("calibratedEdgePct"),
        "calibrationBucket": row.get("calibrationBucket"),
        "finalEngineDecision": row.get("finalEngineDecision"),
        "finalGrade": row.get("finalGrade"),
        "finalReason": row.get("finalReason"),
        "marketSource": row.get("priceSource") or row.get("priceSourceUsed") or "unknown",
        "paperOnly": True
    }

def main():
    snapshot_at = datetime.utcnow().isoformat() + "Z"

    signals = read_json(INPUT, [])
    ledger = read_json(LEDGER_JSON, [])

    if not isinstance(signals, list):
        signals = []
    if not isinstance(ledger, list):
        ledger = []

    new_rows = [snapshot_row(r, snapshot_at) for r in signals]
    ledger.extend(new_rows)

    write_json(LEDGER_JSON, ledger)

    fields = sorted({k for r in ledger for k in r.keys()})
    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(ledger)

    by_game = {}
    for r in ledger:
        key = f"{r.get('gameId')}|{r.get('pick')}"
        by_game.setdefault(key, []).append(r)

    lines = []
    lines.append("ASTRODDS 22 ODDS SNAPSHOT LEDGER REPORT")
    lines.append("=" * 46)
    lines.append("")
    lines.append("Goal:")
    lines.append("Create a free historical odds/edge ledger from every engine scan.")
    lines.append("")
    lines.append(f"Snapshot time: {snapshot_at}")
    lines.append(f"Input signals: {len(signals)}")
    lines.append(f"Added snapshots: {len(new_rows)}")
    lines.append(f"Total snapshot rows: {len(ledger)}")
    lines.append(f"Tracked game/pick pairs: {len(by_game)}")
    lines.append("")
    lines.append("Latest snapshots:")

    for r in new_rows:
        market = fnum(r.get("marketProbability"))
        cal = fnum(r.get("calibratedProbabilityV2"))
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Market={round(market * 100, 2) if market is not None else '-'}% | "
            f"Calibrated={round(cal * 100, 2) if cal is not None else '-'}% | "
            f"CalEdge={r.get('calibratedEdgePct')}% | "
            f"Decision={r.get('finalEngineDecision')} | Grade={r.get('finalGrade')}"
        )

    lines.append("")
    lines.append("Next:")
    lines.append("- Run this script every time the engine scans.")
    lines.append("- After multiple snapshots, calculate opening line, last line, movement, and CLV.")
    lines.append("- This becomes ASTRODDS own free historical odds database.")
    lines.append("")
    lines.append(f"JSON: {LEDGER_JSON}")
    lines.append(f"CSV: {LEDGER_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
