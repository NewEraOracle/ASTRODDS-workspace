from pathlib import Path
from datetime import datetime, timezone
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-only-current-edge-latest.json"
REPORT = REPORTS / "219_moneyline_recompute_current_edge_report.txt"

STATUS_ORDER = {"OFFICIAL": 0, "A_PAPER": 1, "REVIEW": 2, "WATCH": 3, "BLOCKED": 4, "NO_BET": 5}

def fnum(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%", "").replace("+", "").replace(",", ".")
    if not s:
        return default
    try:
        return float(s)
    except Exception:
        return default

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def started_or_final(row):
    text = " ".join([
        str(row.get("candidateReasons", "")),
        str(row.get("mlbStatus", "")),
        str(row.get("mainReason", "")),
        str(row.get("riskReason", "")),
    ]).lower()
    return (
        "already_started_or_final" in text
        or "in progress" in text
        or "final" in text
        or "game is already started" in text
    )

def status_from_current_edge(edge_pct, blocked):
    if blocked:
        return "BLOCKED"
    if edge_pct is None:
        return "NO_BET"
    if edge_pct >= 12:
        return "REVIEW"
    if edge_pct >= 6:
        return "WATCH"
    return "NO_BET"

def score_from_current_edge(model, price, edge_pct, blocked):
    if model is None:
        return 0
    score = model * 100
    if edge_pct is not None:
        score += edge_pct
    if blocked:
        score -= 40
    return round(max(-99, min(99, score)), 2)

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load_json(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    recomputed = 0
    positive = 0
    negative = 0
    blocked = 0
    no_model = 0

    for r in rows:
        model = fnum(r.get("modelProbability"), None)
        price = fnum(r.get("price"), None)

        # Preserve old 292 edge as candidateEdgePct because it can be based on a different cached market price.
        old_edge = fnum(r.get("edgePct"), None)
        if old_edge is not None and "candidateEdgePct" not in r:
            r["candidateEdgePct"] = old_edge

        if model is None or price is None:
            r["currentEdgePct"] = ""
            if model is None:
                no_model += 1
            continue

        current_edge = round((model - price) * 100.0, 2)
        r["currentEdgePct"] = current_edge
        r["edgePct"] = current_edge

        is_blocked = started_or_final(r)
        if is_blocked:
            blocked += 1

        new_status = status_from_current_edge(current_edge, is_blocked)
        r["status"] = new_status
        r["telegramEligible"] = False
        r["baseballPredScore"] = score_from_current_edge(model, price, current_edge, is_blocked)

        if is_blocked:
            r["mainReason"] = "Current edge recomputed, but game is already started/final."
            r["riskReason"] = f"Blocked from betting. Current edge {current_edge}% from model {round(model*100,1)}% vs market {round(price*100,1)}%."
        elif current_edge > 0:
            positive += 1
            r["mainReason"] = "Current market edge is positive after recomputing model - price."
            r["riskReason"] = f"Current edge {current_edge}% from model {round(model*100,1)}% vs market {round(price*100,1)}%. Dashboard only until live gate approves."
        else:
            negative += 1
            r["mainReason"] = "No current value edge after recomputing model - price."
            r["riskReason"] = f"Current edge {current_edge}% from model {round(model*100,1)}% vs market {round(price*100,1)}%."

        recomputed += 1

    rows.sort(key=lambda x: (STATUS_ORDER.get(x.get("status", "NO_BET"), 9), -fnum(x.get("currentEdgePct"), -999), -fnum(x.get("baseballPredScore"), 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    counts = {}
    for r in rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "recomputedRows": recomputed,
        "positiveCurrentEdgeRows": positive,
        "negativeCurrentEdgeRows": negative,
        "blockedStartedOrFinalRows": blocked,
        "noModelRows": no_model,
        "counts": counts,
        "moneylineBoard": rows,
        "rule": "MONEYLINE ONLY. Recompute edge using current board price. Telegram unchanged.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({
        "generatedAt": out["generatedAt"],
        "moneylineRows": len(rows),
        "counts": counts,
        "moneylineBoard": rows,
        "rule": out["rule"],
    }, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 219 MONEYLINE RECOMPUTE CURRENT EDGE",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows: {out['rows']}",
        f"Recomputed rows: {out['recomputedRows']}",
        f"Positive current edge rows: {out['positiveCurrentEdgeRows']}",
        f"Negative current edge rows: {out['negativeCurrentEdgeRows']}",
        f"Blocked started/final rows: {out['blockedStartedOrFinalRows']}",
        f"No model rows: {out['noModelRows']}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "CURRENT EDGE MONEYLINE BOARD:"]
    for r in rows[:80]:
        lines.append(
            f"- #{r['rank']} | {r.get('status')} | {r.get('pick')} | {r.get('game')} | "
            f"price={r.get('price')} | model={r.get('modelProbability')} | currentEdge={r.get('currentEdgePct')} | "
            f"candidateEdge={r.get('candidateEdgePct','')} | score={r.get('baseballPredScore')} | mlbStatus={r.get('mlbStatus','')} | {r.get('mainReason')}"
        )
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: MONEYLINE ONLY. Telegram unchanged."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
