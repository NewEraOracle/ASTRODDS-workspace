from pathlib import Path
import json
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parents[1]

LEDGER = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
CLV = WORKSPACE / ".astrodds" / "ASTRODDS-clv-line-movement-latest.json"

OUT_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-daily-performance-latest.json"
PUBLIC_JSON = WORKSPACE / "public" / "astrodds-daily-performance.json"
REPORT = BASE / "reports" / "33_daily_performance_report.txt"

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
            return 0.0
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0

def pct(x):
    if x is None:
        return "N/A"
    return f"{round(x * 100, 2)}%"

def main():
    ledger = read_json(LEDGER, [])
    clv_rows = read_json(CLV, [])

    if not isinstance(ledger, list):
        ledger = []
    if not isinstance(clv_rows, list):
        clv_rows = []

    total = len(ledger)
    wins = sum(1 for r in ledger if r.get("result") == "win")
    losses = sum(1 for r in ledger if r.get("result") == "loss")
    pending = sum(1 for r in ledger if r.get("result") == "pending")
    resolved = wins + losses

    profit = round(sum(fnum(r.get("paperProfitUnits")) for r in ledger), 3)
    win_rate = (wins / resolved) if resolved else None

    by_decision = {}
    by_grade = {}
    by_result = {}

    for r in ledger:
        d = r.get("finalEngineDecision") or "UNKNOWN"
        g = r.get("finalGrade") or "UNKNOWN"
        result = r.get("result") or "pending"

        by_decision[d] = by_decision.get(d, 0) + 1
        by_grade[g] = by_grade.get(g, 0) + 1
        by_result[result] = by_result.get(result, 0) + 1

    engine_buys = [r for r in ledger if r.get("finalEngineDecision") == "ENGINE_BUY"]
    pending_rows = [r for r in ledger if r.get("result") == "pending"]

    best_signal = None
    if ledger:
        best_signal = sorted(
            ledger,
            key=lambda r: fnum(r.get("calibratedEdgePct")),
            reverse=True
        )[0]

    clv_flat = sum(1 for r in clv_rows if r.get("clvStatus") == "flat")
    clv_positive = sum(1 for r in clv_rows if r.get("clvStatus") == "positive")
    clv_negative = sum(1 for r in clv_rows if r.get("clvStatus") == "negative")

    summary = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "paper_only",
        "totalSignals": total,
        "resolved": resolved,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "winRate": win_rate,
        "paperProfitUnits": profit,
        "byDecision": by_decision,
        "byGrade": by_grade,
        "byResult": by_result,
        "engineBuyCount": len(engine_buys),
        "clv": {
            "trackedRows": len(clv_rows),
            "positive": clv_positive,
            "negative": clv_negative,
            "flat": clv_flat,
        },
        "bestSignal": best_signal,
        "pendingSignals": pending_rows,
        "note": "Paper/manual tracking only. No real-money automation.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 33 DAILY PERFORMANCE REPORT")
    lines.append("=" * 44)
    lines.append(f"Generated: {summary['generatedAt']}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"- Total signals: {total}")
    lines.append(f"- Resolved: {resolved}")
    lines.append(f"- Wins: {wins}")
    lines.append(f"- Losses: {losses}")
    lines.append(f"- Pending: {pending}")
    lines.append(f"- Win rate: {pct(win_rate)}")
    lines.append(f"- Paper profit: {profit}u")
    lines.append(f"- ENGINE_BUY count: {len(engine_buys)}")
    lines.append("")
    lines.append("By decision:")
    for k, v in sorted(by_decision.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("By grade:")
    for k, v in sorted(by_grade.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("CLV summary:")
    lines.append(f"- Tracked rows: {len(clv_rows)}")
    lines.append(f"- Positive: {clv_positive}")
    lines.append(f"- Negative: {clv_negative}")
    lines.append(f"- Flat: {clv_flat}")

    if best_signal:
        lines.append("")
        lines.append("Best signal by calibrated edge:")
        lines.append(
            f"- {best_signal.get('game')} | Pick: {best_signal.get('pick')} | "
            f"Decision: {best_signal.get('finalEngineDecision')} | "
            f"Grade: {best_signal.get('finalGrade')} | "
            f"Edge: {best_signal.get('calibratedEdgePct')}% | "
            f"Result: {best_signal.get('result')}"
        )

    if pending_rows:
        lines.append("")
        lines.append("Pending signals:")
        for r in pending_rows:
            lines.append(
                f"- {r.get('date')} | {r.get('game')} | Pick: {r.get('pick')} | "
                f"Decision: {r.get('finalEngineDecision')} | Grade: {r.get('finalGrade')}"
            )

    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"Public JSON: {PUBLIC_JSON}")
    lines.append("")
    lines.append("Rule: Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
