from pathlib import Path
import json
import csv
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

AUDIT = ROOT / ".astrodds" / "ASTRODDS-official-buy-blocker-audit-latest.json"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-soft-hard-context-gate-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-soft-hard-context-gate-latest.csv"
REPORT = BASE / "reports" / "70_soft_hard_context_gate_report.txt"
POLICY = BASE / "models" / "ASTRODDS_SOFT_HARD_CONTEXT_GATE_POLICY.json"

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

def fnum(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).replace(",", "."))
    except Exception:
        return None

def decide(row):
    decision = str(row.get("decision") or "").upper()
    grade = str(row.get("grade") or "").upper()
    edge = fnum(row.get("calibratedEdgePct"))
    market = fnum(row.get("marketProbability"))
    entry = fnum(row.get("entryMax"))
    hard = int(row.get("hardBlockerCount") or 0)
    soft = int(row.get("softWarningCount") or 0)

    reasons = []

    if decision == "ENGINE_BUY":
        return True, "already_engine_buy", ["already_engine_buy"]

    if decision != "MANUAL_REVIEW":
        reasons.append("decision_not_manual_review_value_candidate")
    if grade not in ["A+", "A"]:
        reasons.append("grade_not_A_or_A_plus")
    if edge is None:
        reasons.append("edge_missing")
    if market is None:
        reasons.append("market_missing")
    if entry is None:
        reasons.append("entry_missing")
    if market is not None and entry is not None and market > entry:
        reasons.append("price_above_entry")
    if hard > 0:
        reasons.append("hard_blockers_present")

    if reasons:
        return False, "not_eligible", reasons

    # Smart promotion rules.
    # No hard blockers always required.
    # Strong edge can tolerate a limited number of soft warnings.
    if edge >= 12.0 and soft <= 2:
        return True, "promote_strong_edge_with_limited_soft_context", [f"edge_{edge}_soft_{soft}"]
    if edge >= 10.0 and soft <= 1:
        return True, "promote_good_edge_with_one_soft_context", [f"edge_{edge}_soft_{soft}"]
    if edge >= 7.0 and soft == 0:
        return True, "promote_clean_minimum_edge", [f"edge_{edge}_soft_{soft}"]

    return False, "soft_context_too_heavy_for_edge", [f"edge_{edge}_soft_{soft}"]

def main():
    generated = datetime.now(timezone.utc).isoformat()
    audit = read_json(AUDIT, [])
    if not isinstance(audit, list):
        audit = []

    out = []
    for row in audit:
        eligible, status, reasons = decide(row)
        out.append({
            "snapshotTime": generated,
            **row,
            "promotionEligible": eligible,
            "promotionStatus": status,
            "promotionReasons": "|".join(reasons),
            "targetFinalDecision": "ENGINE_BUY" if eligible else row.get("decision"),
            "targetFinalGrade": row.get("grade"),
            "paperOnly": True,
        })

    write_json(OUT_JSON, out)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "snapshotTime", "gameId", "date", "game", "pick", "decision", "grade",
        "marketProbability", "calibratedProbability", "calibratedEdgePct", "entryMax",
        "hardBlockerCount", "softWarningCount", "hardBlockers", "softWarnings",
        "promotionEligible", "promotionStatus", "promotionReasons", "targetFinalDecision", "targetFinalGrade", "paperOnly"
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in out:
            writer.writerow({k: r.get(k, "") for k in fields})

    policy = {
        "version": "ASTRODDS_SOFT_HARD_CONTEXT_GATE_POLICY_V1",
        "createdAt": generated,
        "status": "OK",
        "target": "1-3 official picks per day when value exists; never force picks.",
        "hardBlockers": "Always block official buy.",
        "softWarnings": "Can be tolerated only with strong edge and price under entry max.",
        "promotionRules": [
            "MANUAL_REVIEW A/A+ only",
            "market price must be <= entry max",
            "no hard blockers",
            "edge >= 12% allows up to 2 soft warnings",
            "edge >= 10% allows up to 1 soft warning",
            "edge >= 7% requires zero soft warnings",
        ],
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    eligible = sum(1 for r in out if r.get("promotionEligible"))
    lines = []
    lines.append("ASTRODDS 70 SOFT/HARD CONTEXT GATE REPORT")
    lines.append("=" * 52)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Input audit rows: {len(audit)}")
    lines.append(f"Promotion eligible rows: {eligible}")
    lines.append("")
    lines.append("Rows:")
    for r in out:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | Eligible={r.get('promotionEligible')} | "
            f"Status={r.get('promotionStatus')} | Reasons={r.get('promotionReasons')}"
        )
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: context gate only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()