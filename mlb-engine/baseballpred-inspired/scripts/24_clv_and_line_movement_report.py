from pathlib import Path
import csv
import json
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

INPUT = WORKSPACE / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.json"
OUT_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-clv-line-movement-latest.json"
OUT_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-clv-line-movement-latest.csv"
REPORT = ROOT / "reports" / "24_clv_and_line_movement_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def parse_time(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return datetime.min

def pct_points(a, b):
    if a is None or b is None:
        return None
    return round((b - a) * 100, 2)

def classify_clv(open_market, latest_market):
    if open_market is None or latest_market is None:
        return "missing"

    move = (latest_market - open_market) * 100

    if move >= 2:
        return "strong_positive_clv"
    if move >= 0.5:
        return "positive_clv"
    if move <= -2:
        return "strong_negative_clv"
    if move <= -0.5:
        return "negative_clv"

    return "flat"

def main():
    rows = read_json(INPUT, [])

    if not isinstance(rows, list):
        rows = []

    grouped = defaultdict(list)

    for r in rows:
        key = f"{r.get('gameId')}|{r.get('pick')}"
        grouped[key].append(r)

    output = []

    for key, group in grouped.items():
        group.sort(key=lambda r: parse_time(r.get("snapshotAt")))

        first = group[0]
        latest = group[-1]

        open_market = fnum(first.get("marketProbability"))
        latest_market = fnum(latest.get("marketProbability"))

        open_cal = fnum(first.get("calibratedProbabilityV2"))
        latest_cal = fnum(latest.get("calibratedProbabilityV2"))

        open_edge = fnum(first.get("calibratedEdgePct"))
        latest_edge = fnum(latest.get("calibratedEdgePct"))

        market_move = pct_points(open_market, latest_market)
        cal_move = pct_points(open_cal, latest_cal)

        edge_decay = None
        if open_edge is not None and latest_edge is not None:
            edge_decay = round(latest_edge - open_edge, 2)

        clv_status = classify_clv(open_market, latest_market)

        output.append({
            "gameId": first.get("gameId"),
            "gamePk": first.get("gamePk"),
            "date": first.get("date"),
            "game": first.get("game"),
            "pick": first.get("pick"),
            "snapshots": len(group),

            "firstSnapshotAt": first.get("snapshotAt"),
            "latestSnapshotAt": latest.get("snapshotAt"),

            "openingMarketProbability": open_market,
            "latestMarketProbability": latest_market,
            "marketMovementPctPoints": market_move,

            "openingCalibratedProbability": open_cal,
            "latestCalibratedProbability": latest_cal,
            "calibratedProbabilityMovementPctPoints": cal_move,

            "openingCalibratedEdgePct": open_edge,
            "latestCalibratedEdgePct": latest_edge,
            "edgeDecayPctPoints": edge_decay,

            "clvStatus": clv_status,
            "finalEngineDecision": latest.get("finalEngineDecision"),
            "finalGrade": latest.get("finalGrade"),
            "marketSource": latest.get("marketSource"),
        })

    output.sort(
        key=lambda r: (
            r.get("clvStatus") != "strong_positive_clv",
            r.get("clvStatus") != "positive_clv",
            -(r.get("latestCalibratedEdgePct") or -999)
        )
    )

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    fields = sorted({k for r in output for k in r.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(output)

    status_counts = {}
    for r in output:
        status = r.get("clvStatus", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    lines = []
    lines.append("ASTRODDS 24 CLV AND LINE MOVEMENT REPORT")
    lines.append("=" * 48)
    lines.append("")
    lines.append("Goal:")
    lines.append("Measure opening vs latest market probability to estimate line movement and CLV.")
    lines.append("")
    lines.append(f"Input snapshot rows: {len(rows)}")
    lines.append(f"Tracked game/pick pairs: {len(output)}")
    lines.append("")

    lines.append("CLV status counts:")
    for k, v in sorted(status_counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Line movement:")
    for r in output:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Snapshots={r.get('snapshots')} | "
            f"OpenMarket={round((r.get('openingMarketProbability') or 0) * 100, 2)}% | "
            f"LatestMarket={round((r.get('latestMarketProbability') or 0) * 100, 2)}% | "
            f"MarketMove={r.get('marketMovementPctPoints')} pts | "
            f"OpenEdge={r.get('openingCalibratedEdgePct')}% | "
            f"LatestEdge={r.get('latestCalibratedEdgePct')}% | "
            f"EdgeDecay={r.get('edgeDecayPctPoints')} pts | "
            f"CLV={r.get('clvStatus')} | "
            f"Decision={r.get('finalEngineDecision')} | Grade={r.get('finalGrade')}"
        )

    lines.append("")
    lines.append("Interpretation:")
    lines.append("- Positive CLV means the market moved toward ASTRODDS pick after the snapshot.")
    lines.append("- Negative CLV means the market moved against ASTRODDS pick.")
    lines.append("- Flat means not enough movement yet.")
    lines.append("- This is not final ROI; it is market validation / line movement tracking.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
