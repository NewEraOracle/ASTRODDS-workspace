from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT.parents[1] / ".astrodds" / "VVS-bullpen-context-latest.json"
CALIBRATION = ROOT / "models" / "ASTRODDS_MLB_CALIBRATION_V2.json"

OUT_JSON = ROOT.parents[1] / ".astrodds" / "VVS-calibrated-edge-latest.json"
OUT_CSV = ROOT.parents[1] / ".astrodds" / "VVS-calibrated-edge-latest.csv"
REPORT = ROOT / "reports" / "16_live_calibrated_edge_gate_report.txt"

def read_json(path):
    if not path.exists():
        return [] if path.name.endswith(".json") and "VVS" in path.name else {}
    return json.loads(path.read_text(encoding="utf-8-sig"))

def to_float(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def bucket_from_gap_pct(gap_pct):
    gap = to_float(gap_pct)
    if gap is None:
        return "missing"

    # modelGapPct is stored as percent, like 52.0, not 0.52
    g = gap / 100

    if g < 0.01:
        return "0-1%"
    if g < 0.02:
        return "1-2%"
    if g < 0.03:
        return "2-3%"
    if g < 0.05:
        return "3-5%"
    if g < 0.08:
        return "5-8%"
    if g < 0.12:
        return "8-12%"
    if g < 0.20:
        return "12-20%"
    return "20%+"

def classify(row):
    edge = to_float(row.get("calibratedEdgePct"))
    market = to_float(row.get("marketProbability"))
    bp_flags = str(row.get("bullpenContextFlags", "none"))
    pitcher_flags = str(row.get("pitcherContextFlags", "none"))
    away_lineup = row.get("awayLineupStatus")
    home_lineup = row.get("homeLineupStatus")

    reasons = []

    if edge is None:
        return "reject", "missing calibrated edge"

    if market is None:
        return "reject", "missing market probability"

    if market < 0.30 or market > 0.75:
        return "reject", "market probability outside 30-75% range"

    if edge < 3:
        return "watch", f"calibrated edge too small: {edge:.2f}%"

    if "high" in bp_flags:
        reasons.append("bullpen fatigue warning")

    if away_lineup != "confirmed" or home_lineup != "confirmed":
        reasons.append("lineup not fully confirmed")

    if "stats_missing" in pitcher_flags:
        reasons.append("pitcher stats missing")

    if edge >= 7 and not reasons:
        return "vvs_buy", f"strong calibrated edge {edge:.2f}% with clean context"

    if edge >= 5:
        if reasons:
            return "manual_review", f"good calibrated edge {edge:.2f}% but " + ", ".join(reasons)
        return "vvs_buy", f"good calibrated edge {edge:.2f}%"

    if edge >= 3:
        if reasons:
            return "manual_review", f"small calibrated edge {edge:.2f}% but " + ", ".join(reasons)
        return "small_buy", f"small calibrated edge {edge:.2f}%"

    return "watch", f"edge below threshold: {edge:.2f}%"

def main():
    rows = read_json(INPUT)
    calibration = read_json(CALIBRATION)

    buckets = calibration.get("calibrationBuckets", {})
    output = []

    counts = {}

    for row in rows:
        r = dict(row)

        bucket = bucket_from_gap_pct(r.get("modelGapPct"))
        cal = buckets.get(bucket)

        if cal:
            calibrated_prob = to_float(cal.get("probability"))
        else:
            calibrated_prob = to_float(calibration.get("globalTrainProbability"))

        market = to_float(r.get("marketProbability"))
        raw_model = to_float(r.get("modelProbability"))

        calibrated_edge = None
        raw_edge = None

        if calibrated_prob is not None and market is not None:
            calibrated_edge = (calibrated_prob - market) * 100

        if raw_model is not None and market is not None:
            raw_edge = (raw_model - market) * 100

        r["calibrationBucket"] = bucket
        r["rawModelProbability"] = raw_model
        r["calibratedProbabilityV2"] = round(calibrated_prob, 6) if calibrated_prob is not None else ""
        r["rawEdgePct"] = round(raw_edge, 2) if raw_edge is not None else ""
        r["calibratedEdgePct"] = round(calibrated_edge, 2) if calibrated_edge is not None else ""

        decision, reason = classify(r)

        r["calibratedDecision"] = decision
        r["calibratedDecisionReason"] = reason

        counts[decision] = counts.get(decision, 0) + 1
        output.append(r)

    output.sort(
        key=lambda x: to_float(x.get("calibratedEdgePct")) if to_float(x.get("calibratedEdgePct")) is not None else -999,
        reverse=True
    )

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    fieldnames = sorted({k for row in output for k in row.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(output)

    lines = []
    lines.append("ASTRODDS 16 LIVE CALIBRATED EDGE GATE")
    lines.append("=" * 42)
    lines.append("")
    lines.append("Goal:")
    lines.append("Replace raw overconfident model probability with calibrated historical probability.")
    lines.append("")
    lines.append(f"Input rows: {len(rows)}")
    lines.append("")
    lines.append("Decision counts:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Calibrated picks:")
    for r in output:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Market={round(to_float(r.get('marketProbability')) * 100, 2) if to_float(r.get('marketProbability')) is not None else '-'}% | "
            f"RawModel={round(to_float(r.get('rawModelProbability')) * 100, 2) if to_float(r.get('rawModelProbability')) is not None else '-'}% | "
            f"Calibrated={round(to_float(r.get('calibratedProbabilityV2')) * 100, 2) if to_float(r.get('calibratedProbabilityV2')) is not None else '-'}% | "
            f"RawEdge={r.get('rawEdgePct')}% | "
            f"CalEdge={r.get('calibratedEdgePct')}% | "
            f"Decision={r.get('calibratedDecision')} | "
            f"Reason={r.get('calibratedDecisionReason')}"
        )

    lines.append("")
    lines.append("Rule:")
    lines.append("- Raw model probability is NOT trusted for betting decisions.")
    lines.append("- Calibrated probability is used for edge.")
    lines.append("- Context warnings can downgrade a pick to manual review.")
    lines.append("- Paper only until live ledger proves results.")
    lines.append("")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
