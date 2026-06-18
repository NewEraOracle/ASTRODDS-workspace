from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_ACTION = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
OUT_FULL = ASTRO / "ASTRODDS-moneyline-status-fallback-confirmed-latest.json"
REPORT = REPORTS / "229_moneyline_strict_live_confirmation_guard_report.txt"

OPEN_STATES = ("scheduled", "pre-game", "pregame", "warmup", "preview")
CLOSED_STATES = ("final", "in progress", "delayed", "postponed", "suspended")

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

def txt(v):
    return str(v or "").lower().strip()

def contains_any(s, terms):
    return any(t in s for t in terms)

def live_status(row):
    return txt(row.get("liveMlbStatus", ""))

def cached_status(row):
    return " ".join([
        txt(row.get("cachedMlbStatus", "")),
        txt(row.get("mlbStatus", "")),
        txt(row.get("cachedCandidateReasons", "")),
        txt(row.get("candidateReasons", "")),
    ]).strip()

def status_decision(row):
    """
    Safer priority:
    1. liveMlbStatus closed => BLOCKED
    2. liveMlbStatus open => OPEN
    3. no liveMlbStatus + cached open => OPEN_FALLBACK
    4. no liveMlbStatus + cached closed => HOLD_STALE_CLOSED, NOT BLOCKED
    5. unknown => HOLD

    Reason: cached "Final/In Progress" can be stale or from an older game/date.
    Only liveMlbStatus can hard-block.
    """
    live = live_status(row)
    cached = cached_status(row)

    if live:
        if contains_any(live, CLOSED_STATES):
            return "BLOCKED", row.get("liveMlbStatus", ""), "liveMlbStatus"
        if contains_any(live, OPEN_STATES):
            return "OPEN", row.get("liveMlbStatus", ""), "liveMlbStatus"
        return "HOLD", row.get("liveMlbStatus", ""), "liveMlbStatus_unknown"

    if cached:
        if contains_any(cached, OPEN_STATES):
            val = row.get("cachedMlbStatus") or row.get("mlbStatus") or "CachedOpen"
            return "OPEN_FALLBACK", val, "cached_open_fallback"
        if "already_started_or_final" in cached or contains_any(cached, CLOSED_STATES):
            val = row.get("cachedMlbStatus") or row.get("mlbStatus") or "CachedClosed"
            return "HOLD_STALE_CLOSED", val, "cached_closed_hold_not_block"

    return "HOLD", "", "no_status"

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
    fallback_open_count = 0
    cached_closed_hold_count = 0

    for raw in rows:
        r = dict(raw)
        model = fnum(r.get("modelProbability"), None)
        price = fnum(r.get("price"), None)
        edge = fnum(r.get("currentEdgePct", r.get("edgePct")), None)

        if model is not None and price is not None:
            edge = round((model - price) * 100, 2)
            r["currentEdgePct"] = edge
            r["edgePct"] = edge

        decision, status_value, status_source = status_decision(r)
        r["statusDecision"] = decision
        r["statusSourceUsed"] = status_source

        if decision == "BLOCKED":
            r["actionStatus"] = "BLOCKED_LIVE_STARTED_OR_FINAL"
            r["status"] = "BLOCKED"
            r["telegramEligible"] = False
            r["mainReason"] = "Blocked because liveMlbStatus confirms game is not pregame."
            r["riskReason"] = f"statusSource={status_source} | status={status_value}"
            blocked.append(r)
            continue

        if decision == "HOLD_STALE_CLOSED":
            cached_closed_hold_count += 1
            r["actionStatus"] = "HOLD_CACHED_CLOSED_NEEDS_LIVE_CONFIRMATION"
            r["status"] = "HOLD"
            r["telegramEligible"] = False
            r["mainReason"] = "Not actionable: cached status says closed, but liveMlbStatus is blank. Treating as HOLD to avoid stale Final/In Progress false block."
            r["riskReason"] = f"cachedStatus={status_value} | liveMlbStatus=blank | needs live confirmation"
            hold_unknown.append(r)
            continue

        if decision == "HOLD":
            r["actionStatus"] = "HOLD_STATUS_NOT_CONFIRMED"
            r["status"] = "HOLD"
            r["telegramEligible"] = False
            r["mainReason"] = "Not actionable: no open status confirmed from live or cached status."
            r["riskReason"] = f"liveMlbStatus={r.get('liveMlbStatus','blank')} | cachedMlbStatus={r.get('cachedMlbStatus','')} | mlbStatus={r.get('mlbStatus','')}"
            hold_unknown.append(r)
            continue

        if decision == "OPEN_FALLBACK":
            fallback_open_count += 1
            if not r.get("liveMlbStatus"):
                r["liveMlbStatus"] = f"Fallback-{status_value}"
            r["mainReason"] = "Open status confirmed by cached fallback because liveMlbStatus was blank."

        if model is None or price is None:
            r["actionStatus"] = "NO_MODEL_OR_PRICE"
            r["status"] = "NO_BET"
            r["telegramEligible"] = False
            r["mainReason"] = "Status is open, but model or price is missing."
            r["riskReason"] = "Need both modelProbability and market price."
            missing.append(r)
            continue

        tier = action_tier(edge)
        r["actionStatus"] = tier
        r["status"] = display_status(tier)
        r["telegramEligible"] = False

        if tier == "NO_BET":
            r["mainReason"] = "Status open, but edge is not high enough."
            r["riskReason"] = f"Current edge {edge}%."
            no_value.append(r)
        else:
            r["mainReason"] = "Moneyline candidate with open status confirmation."
            r["riskReason"] = f"statusSource={status_source}; status={status_value}; edge {edge}% from model {round(model*100,1)}% vs market {round(price*100,1)}%."
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
        "fallbackOpenRows": fallback_open_count,
        "cachedClosedHoldRows": cached_closed_hold_count,
        "holdUnknownRows": len(hold_unknown),
        "blockedRows": len(blocked),
        "noValueRows": len(no_value),
        "missingModelOrPriceRows": len(missing),
        "actionableMoneyline": actionable,
        "holdMoneyline": hold_unknown,
        "blockedMoneyline": blocked,
        "noValueMoneyline": no_value,
        "missingModelOrPrice": missing,
        "rule": "liveMlbStatus hard-blocks. Cached open can fallback. Cached closed without liveMlbStatus becomes HOLD, not BLOCKED.",
    }

    OUT_ACTION.write_text(json.dumps(out, indent=2), encoding="utf-8")
    OUT_FULL.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineBoard": all_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")
    IN_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(all_rows), "moneylineBoard": all_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 229 MONEYLINE STATUS FALLBACK CONFIRMATION GUARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Input rows: {out['inputRows']}",
        f"Actionable rows: {out['actionableRows']}",
        f"Fallback open rows: {out['fallbackOpenRows']}",
        f"Cached closed hold rows: {out['cachedClosedHoldRows']}",
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
                f"status={r.get('liveMlbStatus','')} | source={r.get('statusSourceUsed','')} | stake={r.get('suggestedStake','')}"
            )

    lines += ["", "HOLD / NOT ACTIONABLE:"]
    for r in hold_unknown[:60]:
        lines.append(
            f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | edge={r.get('currentEdgePct', r.get('edgePct'))} | "
            f"live={r.get('liveMlbStatus','blank')} | cached={r.get('cachedMlbStatus','')} | mlbStatus={r.get('mlbStatus','')} | {r.get('mainReason')}"
        )

    lines += ["", f"JSON: {OUT_ACTION}", "Rule: cached closed cannot hard-block without liveMlbStatus."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
