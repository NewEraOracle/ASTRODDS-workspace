from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_ACTION = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
OUT_FULL = ASTRO / "ASTRODDS-moneyline-strict-live-confirmed-latest.json"
REPORT = REPORTS / "229_moneyline_strict_live_confirmation_guard_report.txt"

OPEN_STATES = ("scheduled", "pre-game", "pregame", "warmup", "preview")
CLOSED_STATES = ("final", "in progress", "live", "delayed", "postponed", "suspended")

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

def status_text(row):
    return " ".join([
        str(row.get("liveMlbStatus", "")),
        str(row.get("mlbStatus", "")),
        str(row.get("liveStatusSource", "")),
    ]).lower().strip()

def cached_text(row):
    return " ".join([
        str(row.get("cachedMlbStatus", "")),
        str(row.get("cachedCandidateReasons", "")),
        str(row.get("candidateReasons", "")),
    ]).lower().strip()

def live_is_open(row):
    txt = status_text(row)
    if not txt:
        return False
    return any(x in txt for x in OPEN_STATES) and not any(x in txt for x in CLOSED_STATES)

def live_is_closed(row):
    txt = status_text(row)
    return any(x in txt for x in CLOSED_STATES)

def cached_is_closed(row):
    txt = cached_text(row)
    return any(x in txt for x in CLOSED_STATES) or "already_started_or_final" in txt

def action_tier(edge):
    if edge is None:
        return "NO_BET"
    if edge >= 12:
        return "A_PICK"
    if edge >= 8:
        return "VALUE_LEAN"
    if edge >= 5:
        return "ACTION_LEAN"
    return "NO_BET"

def display_status(action):
    if action in ("A_PICK", "VALUE_LEAN"):
        return "REVIEW"
    if action == "ACTION_LEAN":
        return "WATCH"
    if action.startswith("HOLD"):
        return "HOLD"
    if action.startswith("BLOCKED"):
        return "BLOCKED"
    return "NO_BET"

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load_json(IN_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    actionable = []
    hold_unknown = []
    blocked = []
    no_value = []
    missing = []

    for r in rows:
        r = dict(r)
        model = fnum(r.get("modelProbability"), None)
        price = fnum(r.get("price"), None)
        edge = fnum(r.get("currentEdgePct", r.get("edgePct")), None)

        if model is not None and price is not None:
            edge = round((model - price) * 100, 2)
            r["currentEdgePct"] = edge
            r["edgePct"] = edge

        live_open = live_is_open(r)
        live_closed = live_is_closed(r)
        cached_closed = cached_is_closed(r)
        live_status = str(r.get("liveMlbStatus", "")).strip()
        source = str(r.get("liveStatusSource", "")).strip()

        if live_closed:
            r["actionStatus"] = "BLOCKED_LIVE_STARTED_OR_FINAL"
            r["status"] = "BLOCKED"
            r["mainReason"] = "Blocked because live MLB status says game is not pregame."
            r["riskReason"] = f"liveMlbStatus={live_status}"
            blocked.append(r)
            continue

        if not live_open:
            # Important fix: never make a bet when live status is blank/no-match.
            if cached_closed:
                r["actionStatus"] = "HOLD_LIVE_STATUS_MISSING_CACHED_CLOSED"
                r["status"] = "HOLD"
                r["mainReason"] = "Not actionable: live MLB status was not confirmed open, and cached status suggests started/final."
                r["riskReason"] = f"liveMlbStatus={live_status or 'blank'} | source={source or 'blank'} | cachedMlbStatus={r.get('cachedMlbStatus','')}"
                hold_unknown.append(r)
            else:
                r["actionStatus"] = "HOLD_LIVE_STATUS_NOT_CONFIRMED_OPEN"
                r["status"] = "HOLD"
                r["mainReason"] = "Not actionable: live MLB status is not confirmed Scheduled/Pre-Game/Warmup."
                r["riskReason"] = f"liveMlbStatus={live_status or 'blank'} | source={source or 'blank'}"
                hold_unknown.append(r)
            continue

        if model is None or price is None:
            r["actionStatus"] = "NO_MODEL_OR_PRICE"
            r["status"] = "NO_BET"
            r["mainReason"] = "Live status is open, but model or price is missing."
            r["riskReason"] = "Need both modelProbability and market price."
            missing.append(r)
            continue

        tier = action_tier(edge)
        r["actionStatus"] = tier
        r["status"] = display_status(tier)
        r["telegramEligible"] = False

        if tier == "NO_BET":
            r["mainReason"] = "Live status open, but edge is not high enough."
            r["riskReason"] = f"Current edge {edge}%."
            no_value.append(r)
        else:
            r["mainReason"] = "Strict live-confirmed Moneyline candidate."
            r["riskReason"] = f"Live status {live_status}; current edge {edge}% from model {round(model*100,1)}% vs market {round(price*100,1)}%."
            if tier == "A_PICK":
                r["suggestedStake"] = "5% max bankroll"
            elif tier == "VALUE_LEAN":
                r["suggestedStake"] = "1-2% max bankroll"
            else:
                r["suggestedStake"] = "0.5-1% max bankroll"
            actionable.append(r)

    actionable.sort(key=lambda x: -fnum(x.get("currentEdgePct"), -999))
    for i, r in enumerate(actionable, 1):
        r["actionRank"] = i

    all_rows = actionable + hold_unknown + blocked + no_value + missing
    for i, r in enumerate(all_rows, 1):
        r["rank"] = i

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputRows": len(rows),
        "actionableRows": len(actionable),
        "holdUnknownRows": len(hold_unknown),
        "blockedRows": len(blocked),
        "noValueRows": len(no_value),
        "missingModelOrPriceRows": len(missing),
        "actionableMoneyline": actionable,
        "holdMoneyline": hold_unknown,
        "blockedMoneyline": blocked,
        "noValueMoneyline": no_value,
        "missingModelOrPrice": missing,
        "rule": "Strict: actionable only when liveMlbStatus confirms Scheduled/Pre-Game/Warmup. Blank/no-match live status can never be actionable.",
    }

    OUT_ACTION.write_text(json.dumps(out, indent=2), encoding="utf-8")
    OUT_FULL.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineBoard": all_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")
    IN_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(all_rows), "moneylineBoard": all_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 229 MONEYLINE STRICT LIVE CONFIRMATION GUARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Input rows: {out['inputRows']}",
        f"Actionable rows: {out['actionableRows']}",
        f"Hold unknown rows: {out['holdUnknownRows']}",
        f"Blocked rows: {out['blockedRows']}",
        f"No value rows: {out['noValueRows']}",
        f"Missing model/price rows: {out['missingModelOrPriceRows']}",
        "",
        "ACTIONABLE MONEYLINE:",
    ]

    if not actionable:
        lines.append("- none")
    else:
        for r in actionable:
            lines.append(
                f"- #{r['actionRank']} | {r['actionStatus']} | {r.get('pick')} | {r.get('game')} | "
                f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct')}% | "
                f"live={r.get('liveMlbStatus','')} | stake={r.get('suggestedStake','')}"
            )

    lines += ["", "HOLD / NOT ACTIONABLE DUE TO LIVE STATUS:"]
    for r in hold_unknown[:30]:
        lines.append(
            f"- HOLD | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct', r.get('edgePct'))} | "
            f"live={r.get('liveMlbStatus','blank')} | cached={r.get('cachedMlbStatus','')} | {r.get('mainReason')}"
        )

    lines += ["", f"JSON: {OUT_ACTION}", "Rule: blank live status can never produce actionable bet."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
