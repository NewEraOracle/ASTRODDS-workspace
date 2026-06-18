from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "222_moneyline_actionable_guard_report.txt"

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

def blocked(row):
    txt = " ".join([
        str(row.get("status", "")),
        str(row.get("mlbStatus", "")),
        str(row.get("candidateReasons", "")),
        str(row.get("mainReason", "")),
        str(row.get("riskReason", "")),
    ]).lower()
    return (
        "blocked" in txt
        or "already_started_or_final" in txt
        or "in progress" in txt
        or "final" in txt
        or "started" in txt
    )

def tier(edge):
    if edge is None:
        return "NO_BET"
    if edge >= 12:
        return "A_PICK"
    if edge >= 8:
        return "VALUE_LEAN"
    if edge >= 5:
        return "ACTION_LEAN"
    return "NO_BET"

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load_json(IN_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    clean = []
    blocked_rows = []
    missing_model = []
    no_value = []

    for r in rows:
        r = dict(r)
        price = fnum(r.get("price"), None)
        model = fnum(r.get("modelProbability"), None)
        edge = fnum(r.get("currentEdgePct", r.get("edgePct")), None)

        if blocked(r):
            r["actionStatus"] = "BLOCKED_STARTED_OR_FINAL"
            blocked_rows.append(r)
            continue

        if price is None or model is None:
            r["actionStatus"] = "NO_MODEL_OR_PRICE"
            missing_model.append(r)
            continue

        if edge is None:
            edge = round((model - price) * 100, 2)
            r["currentEdgePct"] = edge
            r["edgePct"] = edge

        t = tier(edge)
        r["actionStatus"] = t

        if t == "NO_BET":
            no_value.append(r)
        else:
            clean.append(r)

    clean.sort(key=lambda x: -fnum(x.get("currentEdgePct", x.get("edgePct")), -999))
    for i, r in enumerate(clean, 1):
        r["actionRank"] = i
        if r["actionStatus"] == "A_PICK":
            r["suggestedStake"] = "5% max bankroll"
        elif r["actionStatus"] == "VALUE_LEAN":
            r["suggestedStake"] = "1-2% max bankroll"
        else:
            r["suggestedStake"] = "0.5-1% max bankroll"

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputRows": len(rows),
        "actionableRows": len(clean),
        "blockedRows": len(blocked_rows),
        "missingModelOrPriceRows": len(missing_model),
        "noValueRows": len(no_value),
        "actionableMoneyline": clean,
        "blockedMoneyline": blocked_rows,
        "missingModelOrPrice": missing_model,
        "noValueMoneyline": no_value,
        "rule": "Moneyline only. Actionable means not started/final, has price/model, and current edge >= 5%. No real-money automation.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 222 MONEYLINE ACTIONABLE GUARD",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Input rows: {out['inputRows']}",
        f"Actionable rows: {out['actionableRows']}",
        f"Blocked started/final rows: {out['blockedRows']}",
        f"Missing model/price rows: {out['missingModelOrPriceRows']}",
        f"No value rows: {out['noValueRows']}",
        "",
        "ACTIONABLE MONEYLINE:",
    ]

    if not clean:
        lines.append("- none")
    else:
        for r in clean:
            lines.append(
                f"- #{r['actionRank']} | {r['actionStatus']} | {r.get('pick')} | {r.get('game')} | "
                f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct', r.get('edgePct'))}% | "
                f"stake={r.get('suggestedStake')}"
            )

    lines += ["", "Top blocked value rows:"]
    blocked_value = [r for r in blocked_rows if fnum(r.get("currentEdgePct", r.get("edgePct")), -999) >= 5]
    blocked_value.sort(key=lambda x: -fnum(x.get("currentEdgePct", x.get("edgePct")), -999))
    if not blocked_value:
        lines.append("- none")
    else:
        for r in blocked_value[:20]:
            lines.append(
                f"- BLOCKED | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct', r.get('edgePct'))}% | "
                f"status={r.get('mlbStatus','')} | reason={r.get('riskReason','')}"
            )

    lines += ["", f"JSON: {OUT_JSON}", "Rule: Moneyline only. No real-money automation."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
