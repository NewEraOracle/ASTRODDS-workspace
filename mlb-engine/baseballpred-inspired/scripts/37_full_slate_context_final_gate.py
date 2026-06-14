from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

INPUT = ROOT / ".astrodds" / "VVS-bullpen-context-latest.json"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-final-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-final-latest.csv"
REPORT = BASE / "reports" / "37_full_slate_context_final_gate_report.txt"

def read_json(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, list) else []

def fnum(x):
    try:
        if x is None or x == "":
            return 0.0
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0

def picked_side(row):
    pick = str(row.get("pick") or "")
    if pick == str(row.get("awayTeam") or ""):
        return "away"
    if pick == str(row.get("homeTeam") or ""):
        return "home"
    return "unknown"

def has_flag(text, flag):
    return flag in str(text or "")

def decide(row):
    side = picked_side(row)
    edge = fnum(row.get("edgePct"))
    strict = row.get("strictFullSlateDecision")
    conflict = bool(row.get("oppositeSideConflict"))

    flags = []

    if conflict:
        flags.append("opposite_side_conflict")
        return "BLOCKED_CONFLICT", "Conflict detected on same game.", flags

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

    hard_flags = [
        "picked_pitcher_stats_missing",
        "picked_pitcher_high_era",
        "picked_pitcher_high_whip",
        "picked_bullpen_high_fatigue",
        "picked_side_unknown",
    ]

    has_hard = any(f in flags for f in hard_flags)

    if has_hard:
        return "BLOCKED_CONTEXT_RISK", "Context risk on picked side.", flags

    if flags:
        return "FULL_CONTEXT_REVIEW", "Edge exists but context is not fully clean.", flags

    if strict == "FULL_SLATE_A_REVIEW" and edge >= 8:
        return "FULL_CONTEXT_ENGINE_BUY", "Clean full slate context with strong calibrated edge.", flags

    if edge >= 4:
        return "FULL_CONTEXT_WATCH", "Small/medium context edge.", flags

    return "FULL_CONTEXT_NO_BET", "No strong context edge.", flags

def main():
    rows = read_json(INPUT)
    out = []

    for row in rows:
        decision, reason, flags = decide(row)
        item = dict(row)
        item["fullContextDecision"] = decision
        item["fullContextReason"] = reason
        item["fullContextFlags"] = "|".join(flags) if flags else "none"
        item["fullContextGeneratedAt"] = datetime.utcnow().isoformat() + "Z"
        out.append(item)

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    import csv
    if out:
        keys = list(out[0].keys())
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(out)

    counts = {}
    for row in out:
        d = row.get("fullContextDecision")
        counts[d] = counts.get(d, 0) + 1

    ranked = sorted(out, key=lambda r: fnum(r.get("edgePct")), reverse=True)

    lines = []
    lines.append("ASTRODDS 37 FULL SLATE CONTEXT FINAL GATE REPORT")
    lines.append("=" * 58)
    lines.append(f"Input rows: {len(rows)}")
    lines.append("")
    lines.append("Decision counts:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Ranked context decisions:")
    for r in ranked:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Edge: {r.get('edgePct')}% | "
            f"Decision: {r.get('fullContextDecision')} | "
            f"Flags: {r.get('fullContextFlags')}"
        )

    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: context gate only. Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
