from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

INPUT = WORKSPACE / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
LEDGER_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
LEDGER_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.csv"
REPORT = ROOT / "reports" / "19_engine_signal_ledger_report.txt"

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

def signal_key(row):
    return "|".join([
        str(row.get("gameId", "")),
        str(row.get("date", "")),
        str(row.get("pick", "")),
        str(row.get("engineVersion", "")),
    ])

def compact_signal(row):
    return {
        "ledgerAddedAt": datetime.utcnow().isoformat() + "Z",
        "gameId": row.get("gameId"),
        "gamePk": row.get("gamePk"),
        "date": row.get("date"),
        "game": row.get("game"),
        "awayTeam": row.get("awayTeam"),
        "homeTeam": row.get("homeTeam"),
        "pick": row.get("pick"),

        "engineVersion": row.get("engineVersion"),
        "finalEngineDecision": row.get("finalEngineDecision"),
        "finalGrade": row.get("finalGrade"),
        "finalReason": row.get("finalReason"),

        "marketProbability": row.get("marketProbability"),
        "rawModelProbability": row.get("rawModelProbability"),
        "calibratedProbabilityV2": row.get("calibratedProbabilityV2"),
        "rawEdgePct": row.get("rawEdgePct"),
        "calibratedEdgePct": row.get("calibratedEdgePct"),
        "calibrationBucket": row.get("calibrationBucket"),

        "pitcherContextFlags": row.get("pitcherContextFlags"),
        "bullpenContextFlags": row.get("bullpenContextFlags"),
        "awayLineupStatus": row.get("awayLineupStatus"),
        "homeLineupStatus": row.get("homeLineupStatus"),
        "weatherStatus": row.get("weatherStatus"),

        "result": row.get("result") or "pending",
        "winner": row.get("winner") or "",
        "resolvedAt": row.get("resolvedAt") or "",
        "paperOnly": True,
        "realMoneyApproved": False,
    }

def main():
    signals = read_json(INPUT, [])
    existing = read_json(LEDGER_JSON, [])

    if not isinstance(signals, list):
        signals = []
    if not isinstance(existing, list):
        existing = []

    before_count = len(existing)

    ledger_by_key = {}

    for row in existing:
        ledger_by_key[signal_key(row)] = row

    added = 0
    updated = 0

    for row in signals:
        compact = compact_signal(row)
        key = signal_key(compact)

        if key in ledger_by_key:
            old = ledger_by_key[key]

            # Preserve resolved results if they already exist
            if old.get("result") in ["win", "loss", "push", "void"]:
                compact["result"] = old.get("result")
                compact["winner"] = old.get("winner", "")
                compact["resolvedAt"] = old.get("resolvedAt", "")
                compact["awayRuns"] = old.get("awayRuns", "")
                compact["homeRuns"] = old.get("homeRuns", "")
                compact["mlbResolveStatus"] = old.get("mlbResolveStatus", "")
                compact["paperProfitUnits"] = old.get("paperProfitUnits", "")

            ledger_by_key[key] = compact
            updated += 1
        else:
            ledger_by_key[key] = compact
            added += 1

    ledger = list(ledger_by_key.values())

    decision_counts = {}
    grade_counts = {}
    result_counts = {}

    for row in ledger:
        decision = row.get("finalEngineDecision", "unknown")
        grade = row.get("finalGrade", "unknown")
        result = row.get("result", "pending")

        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        result_counts[result] = result_counts.get(result, 0) + 1

    ledger.sort(
        key=lambda r: (
            str(r.get("date", "")),
            str(r.get("game", "")),
            str(r.get("pick", ""))
        )
    )

    write_json(LEDGER_JSON, ledger)

    fields = sorted({k for row in ledger for k in row.keys()})
    LEDGER_CSV.parent.mkdir(parents=True, exist_ok=True)

    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ledger)

    lines = []
    lines.append("ASTRODDS 19 ENGINE SIGNAL LEDGER REPORT")
    lines.append("=" * 46)
    lines.append("")
    lines.append("Goal:")
    lines.append("Save every final engine signal into a permanent paper-tracking ledger.")
    lines.append("")
    lines.append(f"Input final signals: {len(signals)}")
    lines.append(f"Ledger rows before: {before_count}")
    lines.append(f"Added this run: {added}")
    lines.append(f"Updated this run: {updated}")
    lines.append(f"Ledger rows after: {len(ledger)}")
    lines.append("")

    lines.append("Decision counts:")
    for k, v in sorted(decision_counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Grade counts:")
    for k, v in sorted(grade_counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Result counts:")
    for k, v in sorted(result_counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Latest ledger signals:")
    for row in ledger[-10:]:
        lines.append(
            f"- {row.get('date')} | {row.get('game')} | Pick: {row.get('pick')} | "
            f"Decision: {row.get('finalEngineDecision')} | Grade: {row.get('finalGrade')} | "
            f"CalEdge: {row.get('calibratedEdgePct')}% | Result: {row.get('result')}"
        )

    lines.append("")
    lines.append("Next:")
    lines.append("20_resolve_engine_signal_ledger.py")
    lines.append("Resolve pending ledger rows to win/loss after games finish.")
    lines.append("")
    lines.append(f"JSON: {LEDGER_JSON}")
    lines.append(f"CSV: {LEDGER_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

