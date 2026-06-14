from pathlib import Path
import json
import csv
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

SIGNALS = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-entry-cut-calibration-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-entry-cut-calibration-latest.csv"
REPORT = BASE / "reports" / "62_entry_cut_calibration_lock_report.txt"
POLICY = BASE / "models" / "ASTRODDS_ENTRY_CUT_CALIBRATION_POLICY.json"

ENTRY_BUFFER = 0.07
MIN_ENTRY = 0.01
MAX_ENTRY = 0.99

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

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def prob01(value):
    v = fnum(value)
    if v is None:
        return None
    if v > 1:
        v = v / 100
    if v < 0 or v > 1:
        return None
    return v

def money_text(value):
    if value is None:
        return "missing"
    return f"${value:.2f}"

def pct_text(value):
    if value is None:
        return "missing"
    return f"{round(value * 100, 2)}%"

def entry_cut_from_calibration(row):
    calibrated = prob01(row.get("calibratedProbabilityV2") or row.get("calibratedProbability"))
    if calibrated is None:
        return None
    return round(max(MIN_ENTRY, min(MAX_ENTRY, calibrated - ENTRY_BUFFER)), 2)

def current_market_price(row):
    return prob01(row.get("marketProbability") or row.get("currentMarketProbability") or row.get("marketPrice"))

def is_public_actionable(row):
    decision = str(row.get("finalEngineDecision") or row.get("decision") or "").upper()
    grade = str(row.get("finalGrade") or row.get("grade") or "").upper()
    market = current_market_price(row)
    entry = entry_cut_from_calibration(row)

    return (
        decision == "ENGINE_BUY"
        and grade in ["A+", "A"]
        and market is not None
        and entry is not None
        and market <= entry
    )

def main():
    generated = datetime.now(timezone.utc).isoformat()
    rows = read_json(SIGNALS, [])
    if not isinstance(rows, list):
        rows = []

    output = []
    for row in rows:
        calibrated = prob01(row.get("calibratedProbabilityV2") or row.get("calibratedProbability"))
        market = current_market_price(row)
        entry = entry_cut_from_calibration(row)
        edge_to_cut = None
        current_edge = None

        if calibrated is not None and entry is not None:
            edge_to_cut = round(calibrated - entry, 4)
        if calibrated is not None and market is not None:
            current_edge = round(calibrated - market, 4)

        actionable = is_public_actionable(row)

        block_reason = ""
        if str(row.get("finalEngineDecision") or "").upper() != "ENGINE_BUY":
            block_reason = "not_engine_buy"
        elif str(row.get("finalGrade") or "").upper() not in ["A+", "A"]:
            block_reason = "grade_not_public"
        elif calibrated is None:
            block_reason = "calibrated_probability_missing"
        elif market is None:
            block_reason = "market_price_missing"
        elif entry is None:
            block_reason = "entry_cut_missing"
        elif market > entry:
            block_reason = "market_price_above_entry_cut"
        else:
            block_reason = "send_allowed"

        output.append({
            "snapshotTime": generated,
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "game": row.get("game"),
            "awayTeam": row.get("awayTeam"),
            "homeTeam": row.get("homeTeam"),
            "pick": row.get("pick"),
            "finalEngineDecision": row.get("finalEngineDecision"),
            "finalGrade": row.get("finalGrade"),
            "marketProbability": market,
            "calibratedProbability": calibrated,
            "entryBuffer": ENTRY_BUFFER,
            "entryMax": entry,
            "currentEdge": current_edge,
            "edgeToCut": edge_to_cut,
            "publicActionable": actionable,
            "publicBlockReason": block_reason,
            "publicFormatEntryMax": money_text(entry),
            "publicFormatStake": "5% bankroll",
            "paperOnly": True,
        })

    write_json(OUT_JSON, output)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "snapshotTime", "gameId", "date", "game", "awayTeam", "homeTeam", "pick",
        "finalEngineDecision", "finalGrade", "marketProbability", "calibratedProbability",
        "entryBuffer", "entryMax", "currentEdge", "edgeToCut",
        "publicActionable", "publicBlockReason", "publicFormatEntryMax",
        "publicFormatStake", "paperOnly",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in output:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    policy = {
        "version": "ASTRODDS_ENTRY_CUT_CALIBRATION_POLICY_V1",
        "createdAt": generated,
        "status": "OK",
        "entryMaxFormula": "entryMax = calibratedProbability - entryBuffer",
        "entryBuffer": ENTRY_BUFFER,
        "entryBufferPct": round(ENTRY_BUFFER * 100, 2),
        "example": {
            "calibratedProbability": "0.63",
            "entryBuffer": "0.07",
            "entryMax": "0.56",
            "display": "$0.56 or 56 cents",
        },
        "publicTelegramSendRule": [
            "finalEngineDecision must be ENGINE_BUY",
            "finalGrade must be A+ or A",
            "marketProbability must exist",
            "entryMax must exist",
            "marketProbability must be <= entryMax",
        ],
        "publicMessageRule": "Show only Pick, Game, Entry max, Recommended stake 5% bankroll, and do not chase above Entry max.",
        "outputs": {
            "json": str(OUT_JSON),
            "csv": str(OUT_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    counts = {}
    for r in output:
        key = r.get("publicBlockReason", "unknown")
        counts[key] = counts.get(key, 0) + 1

    actionable_count = sum(1 for r in output if r.get("publicActionable"))

    lines = []
    lines.append("ASTRODDS 62 ENTRY CUT CALIBRATION LOCK REPORT")
    lines.append("=" * 56)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append("Policy:")
    lines.append(f"- Entry buffer: {round(ENTRY_BUFFER * 100, 2)}%")
    lines.append("- Formula: Entry max = calibrated probability - entry buffer")
    lines.append("- Example: 63% bot chance - 7% buffer = $0.56 entry max")
    lines.append("- Public alert sends only if current market price <= entry max")
    lines.append("- Public alert stake: 5% bankroll")
    lines.append("")
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Output rows: {len(output)}")
    lines.append(f"Public actionable rows: {actionable_count}")
    lines.append("")
    lines.append("Block/send reasons:")
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("Entry cut rows:")
    for r in output[:25]:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Decision={r.get('finalEngineDecision')} | Grade={r.get('finalGrade')} | "
            f"Market={money_text(r.get('marketProbability'))} | "
            f"Calibrated={pct_text(r.get('calibratedProbability'))} | "
            f"EntryMax={money_text(r.get('entryMax'))} | "
            f"Actionable={r.get('publicActionable')} | Reason={r.get('publicBlockReason')}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- Entry max is no longer just the current market price.")
    lines.append("- Entry max is a calibrated cut based on bot probability minus safety buffer.")
    lines.append("- If price is above entry max, public Telegram must not send.")
    lines.append("- Paper/manual only. No real-money automation.")
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: entry cut calibration only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

