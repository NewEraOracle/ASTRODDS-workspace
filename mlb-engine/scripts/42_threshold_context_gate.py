from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "mlb-engine" / "baseballpred-inspired" / ".missing"
CONTEXT = ROOT / ".astrodds" / "VVS-bullpen-context-latest.json"
RULES = ROOT / "mlb-engine" / "baseballpred-inspired" / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json"

OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.csv"
REPORT = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports" / "42_threshold_context_gate_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def fnum(x, default=0.0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(str(x).replace(",", "."))
    except Exception:
        return default

def bval(x):
    return str(x).strip().lower() in ["1", "true", "yes"]

def picked_side(row):
    pick = str(row.get("pick") or "")
    if pick == str(row.get("awayTeam") or ""):
        return "away"
    if pick == str(row.get("homeTeam") or ""):
        return "home"
    return "unknown"

def has_flag(text, flag):
    return flag in str(text or "")

def calibrated_probability(row):
    return fnum(
        row.get("modelProbability")
        or row.get("calibratedProbabilityV2")
        or row.get("calibratedProbability")
        or row.get("calibrated_pick_probability_v2")
    )

def decide(row, thresholds):
    prob = calibrated_probability(row)
    strict = str(row.get("strictFullSlateDecision") or "")
    conflict = bval(row.get("oppositeSideConflict"))
    side = picked_side(row)

    engine_buy_min = fnum(thresholds.get("engineBuyStrictCalibratedProbability"), 0.60)
    a_review_min = fnum(thresholds.get("aReviewCoreCalibratedProbability"), 0.58)
    watch_min = fnum(thresholds.get("watchReviewCalibratedProbability"), 0.55)

    flags = []

    if conflict:
        flags.append("opposite_side_conflict")
        return "BLOCKED_CONFLICT", "Opposite-side conflict blocks the pick.", flags

    if strict not in ["FULL_SLATE_A_REVIEW", "FULL_SLATE_B_REVIEW"]:
        flags.append("strict_gate_not_passed")
        return "FULL_CONTEXT_NO_BET", "Strict full slate gate did not pass.", flags

    away_lineup = row.get("awayLineupStatus")
    home_lineup = row.get("homeLineupStatus")
    if away_lineup != "confirmed" or home_lineup != "confirmed":
        flags.append("lineup_not_confirmed")

    pitcher_flags = str(row.get("pitcherContextFlags") or "")
    bullpen_flags = str(row.get("bullpenContextFlags") or "")

    if side == "away":
        if has_flag(pitcher_flags, "away_pitcher_stats_missing"):
            flags.append("picked_pitcher_stats_missing")
        if has_flag(pitcher_flags, "away_pitcher_high_era"):
            flags.append("picked_pitcher_high_era")
        if has_flag(pitcher_flags, "away_pitcher_high_whip"):
            flags.append("picked_pitcher_high_whip")
        if has_flag(bullpen_flags, "away_bullpen_high_fatigue"):
            flags.append("picked_bullpen_high_fatigue")
    elif side == "home":
        if has_flag(pitcher_flags, "home_pitcher_stats_missing"):
            flags.append("picked_pitcher_stats_missing")
        if has_flag(pitcher_flags, "home_pitcher_high_era"):
            flags.append("picked_pitcher_high_era")
        if has_flag(pitcher_flags, "home_pitcher_high_whip"):
            flags.append("picked_pitcher_high_whip")
        if has_flag(bullpen_flags, "home_bullpen_high_fatigue"):
            flags.append("picked_bullpen_high_fatigue")
    else:
        flags.append("picked_side_unknown")

    wind = fnum(row.get("windSpeedKmh"))
    if wind >= 28:
        flags.append("high_wind_weather")

    hard_blocks = ["picked_pitcher_stats_missing", "picked_side_unknown"]
    has_hard_block = any(f in flags for f in hard_blocks)
    context_clean = len(flags) == 0

    if has_hard_block:
        return "BLOCKED_CONTEXT_RISK", "Hard context blocker on picked side.", flags

    if prob >= engine_buy_min and context_clean:
        return "FULL_CONTEXT_ENGINE_BUY_STRICT", "60%+ calibrated probability with clean context.", flags

    if prob >= a_review_min:
        if context_clean:
            return "FULL_CONTEXT_A_REVIEW_CLEAN", "58%+ calibrated probability with clean/reviewable context.", flags
        return "FULL_CONTEXT_A_REVIEW", "58%+ calibrated probability but context requires review.", flags

    if prob >= watch_min:
        return "FULL_CONTEXT_WATCH_REVIEW", "55%+ calibrated probability watch/review zone.", flags

    return "FULL_CONTEXT_NO_BET", "Below validated probability threshold.", flags

def main():
    rows = read_json(CONTEXT, [])
    rules = read_json(RULES, {})
    thresholds = rules.get("lockedThresholds", {})

    out = []
    for r in rows:
        decision, reason, flags = decide(r, thresholds)
        item = dict(r)
        item["thresholdContextDecision"] = decision
        item["thresholdContextReason"] = reason
        item["thresholdContextFlags"] = "|".join(flags) if flags else "none"
        item["thresholdCalibratedProbability"] = calibrated_probability(r)
        item["thresholdRulesVersion"] = rules.get("version")
        item["thresholdContextGeneratedAt"] = datetime.utcnow().isoformat() + "Z"
        out.append(item)

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    if out:
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
            keys = list(out[0].keys())
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(out)

    counts = {}
    for r in out:
        d = r.get("thresholdContextDecision")
        counts[d] = counts.get(d, 0) + 1

    ranked = sorted(out, key=lambda r: fnum(r.get("thresholdCalibratedProbability")), reverse=True)

    lines = []
    lines.append("ASTRODDS 42 THRESHOLD CONTEXT GATE REPORT")
    lines.append("=" * 54)
    lines.append(f"Input rows: {len(rows)}")
    lines.append("")
    lines.append("Decision counts:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Ranked threshold decisions:")
    for r in ranked:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Prob={round(fnum(r.get('thresholdCalibratedProbability')) * 100, 2)}% | "
            f"Edge={r.get('edgePct')}% | "
            f"Decision={r.get('thresholdContextDecision')} | "
            f"Flags={r.get('thresholdContextFlags')}"
        )

    lines.append("")
    lines.append("Locked thresholds used:")
    lines.append(f"- ENGINE_BUY_STRICT: {thresholds.get('engineBuyStrictCalibratedProbability')}")
    lines.append(f"- A_REVIEW_CORE: {thresholds.get('aReviewCoreCalibratedProbability')}")
    lines.append(f"- WATCH_REVIEW: {thresholds.get('watchReviewCalibratedProbability')}")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: threshold context gate only. Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
