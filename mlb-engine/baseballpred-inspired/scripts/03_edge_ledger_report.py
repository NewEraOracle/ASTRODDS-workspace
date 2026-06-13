from pathlib import Path
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / ".astrodds" / "edge-tracking" / "edge-ledger.json"
REPORT = Path(__file__).resolve().parents[1] / "reports" / "03_edge_ledger_report.txt"

def load_ledger():
    if not LEDGER.exists():
        return []
    return json.loads(LEDGER.read_text(encoding="utf-8-sig"))

def main():
    rows = load_ledger()
    buckets = defaultdict(lambda: {"total": 0, "win": 0, "loss": 0, "pending": 0})

    for r in rows:
        bucket = r.get("edgeBucket", "unknown")
        result = r.get("result", "pending")
        buckets[bucket]["total"] += 1
        buckets[bucket][result] = buckets[bucket].get(result, 0) + 1

    lines = []
    lines.append("ASTRODDS 03 EDGE LEDGER REPORT")
    lines.append("=" * 36)
    lines.append(f"Ledger rows: {len(rows)}")
    lines.append("")
    lines.append("Edge buckets:")

    for bucket, data in sorted(buckets.items()):
        total = data["total"]
        wins = data.get("win", 0)
        losses = data.get("loss", 0)
        pending = data.get("pending", 0)
        resolved = wins + losses
        win_rate = round((wins / resolved) * 100, 2) if resolved else None

        lines.append(
            f"{bucket}: total={total} win={wins} loss={losses} pending={pending} winRate={win_rate}"
        )

    lines.append("")
    lines.append("Pending picks:")
    for r in rows:
        if r.get("result", "pending") == "pending":
            lines.append(
                f"- {r.get('date')} | {r.get('awayTeam')} @ {r.get('homeTeam')} | "
                f"Pick: {r.get('pick')} | Edge: {r.get('edgePct')}% | Bucket: {r.get('edgeBucket')}"
            )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

