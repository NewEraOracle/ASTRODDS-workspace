from pathlib import Path
import json
import csv
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENGINE = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
ENTRY = ROOT / ".astrodds" / "ASTRODDS-entry-cut-calibration-latest.json"
INJURY = ROOT / ".astrodds" / "ASTRODDS-free-injury-context-gate-latest.json"

OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-official-buy-blocker-audit-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-official-buy-blocker-audit-latest.csv"
REPORT = BASE / "reports" / "69_official_buy_blocker_audit_report.txt"

ENTRY_BUFFER = 0.07

HARD_KEYWORDS = [
    "market_price_missing",
    "market_price_above_entry_cut",
    "price_above_entry",
    "no_market_price",
    "missing_market_price",
    "pitcher_scratch",
    "probable_pitcher_injured",
    "picked_probable_pitcher_injured",
    "critical_pitcher_match",
    "lineup_confirmed_bad",
    "injury_critical",
    "block_or_admin_review",
    "no_live_data",
    "game_data_missing",
]

SOFT_KEYWORDS = [
    "lineup_not_confirmed",
    "bullpen warning",
    "bullpen_warning",
    "pitcher warning",
    "pitcher_warning",
    "picked_bullpen_high_fatigue",
    "picked_team_medium_recent_injury_context",
    "picked_team_high_recent_injury_cluster",
    "opponent_injury_context",
    "medium injury",
    "injury_context",
]

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

def prob01(v):
    n = fnum(v)
    if n is None:
        return None
    if n > 1:
        n = n / 100
    if n < 0 or n > 1:
        return None
    return n

def pct_value(v):
    n = fnum(v)
    if n is None:
        return None
    if n <= 1:
        n *= 100
    return n

def money(v):
    if v is None:
        return "missing"
    return f"${float(v):.2f}"

def pct(v):
    if v is None:
        return "missing"
    return f"{round(float(v), 2)}%"

def key(row):
    return f"{row.get('gameId') or ''}|{row.get('game') or ''}|{row.get('pick') or ''}"

def by_key(rows):
    out = {}
    for r in rows:
        if isinstance(r, dict):
            out[key(r)] = r
    return out

def get_market(row):
    return prob01(row.get("marketProbability") or row.get("currentMarketProbability") or row.get("marketPrice"))

def get_calibrated(row):
    return prob01(row.get("calibratedProbabilityV2") or row.get("calibratedProbability"))

def get_edge_pct(row):
    e = pct_value(row.get("calibratedEdgePct") or row.get("edge"))
    if e is not None:
        return e
    cal = get_calibrated(row)
    mkt = get_market(row)
    if cal is not None and mkt is not None:
        return (cal - mkt) * 100
    return None

def get_entry(row, entry_row=None):
    if entry_row:
        x = prob01(entry_row.get("entryMax"))
        if x is not None:
            return x
    cal = get_calibrated(row)
    if cal is None:
        return None
    return round(max(0.01, min(0.99, cal - ENTRY_BUFFER)), 2)

def text_flags(row, injury_row=None, entry_row=None):
    parts = []
    for k, v in row.items():
        lk = str(k).lower()
        if any(w in lk for w in ["flag", "reason", "warning", "context"]):
            parts.append(str(v))
    if injury_row:
        for k in ["freeInjuryContextFlags", "officialBuyImpact", "pickedTeamInjuryRisk", "pickedTeamInjuryDetails"]:
            if k in injury_row:
                parts.append(str(injury_row.get(k)))
    if entry_row:
        for k in ["publicBlockReason"]:
            if k in entry_row:
                parts.append(str(entry_row.get(k)))
    return " | ".join(parts).lower()

def classify(row, entry_row=None, injury_row=None):
    decision = str(row.get("finalEngineDecision") or row.get("decision") or "").upper()
    grade = str(row.get("finalGrade") or row.get("grade") or "").upper()

    market = get_market(row)
    calibrated = get_calibrated(row)
    entry = get_entry(row, entry_row)
    edge = get_edge_pct(row)

    hard = []
    soft = []

    if decision in ["WATCH", "NO_BET", "PASS"]:
        hard.append("final_decision_not_value_candidate")
    if grade in ["WATCH", "C", "D", "F"]:
        hard.append("grade_not_public_quality")
    if calibrated is None:
        hard.append("calibrated_probability_missing")
    if market is None:
        hard.append("market_price_missing")
    if entry is None:
        hard.append("entry_cut_missing")
    if market is not None and entry is not None and market > entry:
        hard.append("market_price_above_entry_cut")

    text = text_flags(row, injury_row, entry_row)

    for k in HARD_KEYWORDS:
        if k in text and k not in hard:
            hard.append(k)
    for k in SOFT_KEYWORDS:
        if k in text and k not in soft:
            soft.append(k)

    # If the final engine already set MANUAL_REVIEW and no specific blocker is visible,
    # keep a soft warning so it does not silently auto-promote without context.
    if decision == "MANUAL_REVIEW" and not hard and not soft:
        soft.append("manual_review_unspecified_context")

    return {
        "decision": decision,
        "grade": grade,
        "marketProbability": market,
        "calibratedProbability": calibrated,
        "calibratedEdgePct": edge,
        "entryMax": entry,
        "hardBlockers": hard,
        "softWarnings": soft,
        "hardBlockerCount": len(hard),
        "softWarningCount": len(soft),
    }

def main():
    generated = datetime.now(timezone.utc).isoformat()
    engine = read_json(ENGINE, [])
    entry = read_json(ENTRY, [])
    injury = read_json(INJURY, [])

    if not isinstance(engine, list):
        engine = []
    if not isinstance(entry, list):
        entry = []
    if not isinstance(injury, list):
        injury = []

    entry_map = by_key(entry)
    injury_map = by_key(injury)

    rows = []
    for r in engine:
        if not isinstance(r, dict):
            continue
        e = entry_map.get(key(r))
        inj = injury_map.get(key(r))
        c = classify(r, e, inj)
        rows.append({
            "snapshotTime": generated,
            "gameId": r.get("gameId"),
            "date": r.get("date"),
            "game": r.get("game"),
            "pick": r.get("pick"),
            "decision": c["decision"],
            "grade": c["grade"],
            "marketProbability": c["marketProbability"],
            "calibratedProbability": c["calibratedProbability"],
            "calibratedEdgePct": c["calibratedEdgePct"],
            "entryMax": c["entryMax"],
            "hardBlockerCount": c["hardBlockerCount"],
            "softWarningCount": c["softWarningCount"],
            "hardBlockers": "|".join(c["hardBlockers"]) if c["hardBlockers"] else "none",
            "softWarnings": "|".join(c["softWarnings"]) if c["softWarnings"] else "none",
            "priceOk": bool(c["marketProbability"] is not None and c["entryMax"] is not None and c["marketProbability"] <= c["entryMax"]),
            "paperOnly": True,
        })

    write_json(OUT_JSON, rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "snapshotTime", "gameId", "date", "game", "pick", "decision", "grade",
        "marketProbability", "calibratedProbability", "calibratedEdgePct", "entryMax",
        "hardBlockerCount", "softWarningCount", "hardBlockers", "softWarnings", "priceOk", "paperOnly"
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})

    counts = {}
    for r in rows:
        k = "hard_blocked" if r["hardBlockerCount"] else ("soft_review" if r["softWarningCount"] else "clean")
        counts[k] = counts.get(k, 0) + 1

    lines = []
    lines.append("ASTRODDS 69 OFFICIAL BUY BLOCKER AUDIT REPORT")
    lines.append("=" * 58)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Input engine rows: {len(engine)}")
    lines.append(f"Output audit rows: {len(rows)}")
    lines.append("")
    lines.append("Counts:")
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("Rows:")
    for r in rows:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | Decision={r.get('decision')} | Grade={r.get('grade')} | "
            f"Market={money(r.get('marketProbability'))} | Entry={money(r.get('entryMax'))} | "
            f"Edge={pct(r.get('calibratedEdgePct'))} | Hard={r.get('hardBlockers')} | Soft={r.get('softWarnings')}"
        )
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: blocker audit only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()