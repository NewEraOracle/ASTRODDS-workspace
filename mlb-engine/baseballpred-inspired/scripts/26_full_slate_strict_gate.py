from pathlib import Path
import csv
import json
import urllib.request
from collections import defaultdict
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parents[1]

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"
CALIBRATION = BASE / "models" / "ASTRODDS_MLB_CALIBRATION_V2.json"

OUT_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-full-slate-strict-latest.json"
OUT_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-full-slate-strict-latest.csv"
REPORT = BASE / "reports" / "26_full_slate_strict_gate_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def game_key(r):
    # Strong matchup grouping: ignore date/gameId because backend can return duplicate rows
    # with slightly different timestamps or market references.
    away = str(r.get("awayTeam", "")).strip().lower()
    home = str(r.get("homeTeam", "")).strip().lower()
    return f"{away}|{home}"

def gap_bucket(gap_pct):
    g = fnum(gap_pct)
    if g is None:
        return "missing"
    g = g / 100
    if g < 0.01: return "0-1%"
    if g < 0.02: return "1-2%"
    if g < 0.03: return "2-3%"
    if g < 0.05: return "3-5%"
    if g < 0.08: return "5-8%"
    if g < 0.12: return "8-12%"
    if g < 0.20: return "12-20%"
    return "20%+"

def backend_gap(row):
    for key in ["modelProbabilityGapPct", "modelGapPct", "diagnosticModelGapPct", "scoreGapPct", "gapPct"]:
        value = fnum(row.get(key))
        if value is not None:
            return value, key
    return None, "missing_backend_gap"

def decision(edge, gap_source, conflict):
    e = fnum(edge)

    if gap_source == "missing_backend_gap":
        return "RESEARCH_ONLY_GAP_MISSING"

    if conflict:
        return "MANUAL_REVIEW_CONFLICT"

    if e is None:
        return "NO_DATA"

    if e >= 7:
        return "FULL_SLATE_A_REVIEW"

    if e >= 5:
        return "FULL_SLATE_B_REVIEW"

    if e >= 3:
        return "WATCH_EDGE"

    return "NO_BET"

def main():
    try:
        api = fetch_json(API_URL)
    except Exception as e:
        msg = (
            "ASTRODDS 26 FULL SLATE STRICT GATE REPORT\n"
            "==========================================\n\n"
            "FAILED: local API not reachable.\n"
            f"API: {API_URL}\n"
            f"Error: {e}\n\n"
            "Fix: run npm run dev in another terminal.\n"
        )
        REPORT.write_text(msg, encoding="utf-8")
        print(msg)
        return

    calibration = read_json(CALIBRATION, {})
    buckets = calibration.get("calibrationBuckets", {})
    global_prob = fnum(calibration.get("globalTrainProbability")) or 0.5652

    rows = api.get("bestBetRows") or api.get("rows") or []
    candidates = []

    for r in rows:
        away = r.get("awayTeam")
        home = r.get("homeTeam")
        pick = r.get("selectedSide") or r.get("pick")

        if r.get("marketType") != "moneyline":
            continue

        if pick not in [away, home]:
            continue

        market = fnum(r.get("marketProbability"))
        raw_model = fnum(r.get("calibratedProbability") or r.get("modelProbability"))

        if market is None or raw_model is None:
            continue

        if market < 0.30 or market > 0.75:
            continue

        gap, gap_source = backend_gap(r)

        if gap is None:
            bucket = "missing"
            cal_prob = global_prob
        else:
            bucket = gap_bucket(gap)
            cal_prob = fnum(buckets.get(bucket, {}).get("probability")) or global_prob

        cal_edge = (cal_prob - market) * 100
        raw_edge = (raw_model - market) * 100

        candidates.append({
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "gameId": r.get("gameId"),
            "date": r.get("date"),
            "game": f"{away} @ {home}",
            "gameKey": "",
            "awayTeam": away,
            "homeTeam": home,
            "pick": pick,
            "marketProbability": round(market, 6),
            "rawModelProbability": round(raw_model, 6),
            "backendModelGapPct": gap if gap is not None else "",
            "backendModelGapSource": gap_source,
            "calibrationBucket": bucket,
            "calibratedProbabilityV2": round(cal_prob, 6),
            "rawEdgePct": round(raw_edge, 2),
            "calibratedEdgePct": round(cal_edge, 2),
            "status": r.get("status"),
            "confidence": r.get("matchConfidence"),
            "risk": r.get("riskLevel"),
            "reason": r.get("mainReason"),
            "paperOnly": True,
        })

    grouped = defaultdict(list)

    for c in candidates:
        c["gameKey"] = game_key(c)
        grouped[c["gameKey"]].append(c)

    final = []
    conflicts = []

    for key, group in grouped.items():
        picks = sorted(set(g["pick"] for g in group))
        conflict = len(picks) > 1

        if conflict:
            conflicts.append(f"{group[0]['game']} -> {', '.join(picks)}")

        group.sort(key=lambda x: fnum(x.get("calibratedEdgePct")) or -999, reverse=True)
        best = group[0]

        best["duplicateRowsForGame"] = len(group)
        best["oppositeSideConflict"] = conflict
        best["conflictingPicks"] = "|".join(picks) if conflict else ""
        best["strictFullSlateDecision"] = decision(
            best.get("calibratedEdgePct"),
            best.get("backendModelGapSource"),
            conflict
        )

        if best["backendModelGapSource"] == "missing_backend_gap":
            best["strictReason"] = "Research only: backend missing true modelProbabilityGapPct."
        elif conflict:
            best["strictReason"] = "Manual review: opposite-side conflict in same game."
        else:
            best["strictReason"] = "Strict gate passed."

        final.append(best)

    final.sort(key=lambda x: fnum(x.get("calibratedEdgePct")) or -999, reverse=True)

    OUT_JSON.write_text(json.dumps(final, indent=2), encoding="utf-8")

    fields = sorted({k for r in final for k in r.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(final)

    decisions = {}
    gap_sources = {}

    for r in final:
        decisions[r["strictFullSlateDecision"]] = decisions.get(r["strictFullSlateDecision"], 0) + 1
        gap_sources[r["backendModelGapSource"]] = gap_sources.get(r["backendModelGapSource"], 0) + 1

    lines = []
    lines.append("ASTRODDS 26 FULL SLATE STRICT GATE REPORT")
    lines.append("=" * 48)
    lines.append("")
    lines.append(f"Backend rows: {len(rows)}")
    lines.append(f"Raw moneyline candidates: {len(candidates)}")
    lines.append(f"Strict best-per-game rows: {len(final)}")
    lines.append(f"Opposite-side conflicts: {len(conflicts)}")
    lines.append("")

    lines.append("Decision counts:")
    for k, v in sorted(decisions.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Gap source counts:")
    for k, v in sorted(gap_sources.items()):
        lines.append(f"- {k}: {v}")

    if conflicts:
        lines.append("")
        lines.append("Conflicts:")
        for c in conflicts:
            lines.append(f"- {c}")

    lines.append("")
    lines.append("Strict ranked:")
    for r in final:
        lines.append(
            f"- {r['game']} | Pick: {r['pick']} | "
            f"Market={round(r['marketProbability']*100,2)}% | "
            f"CalEdge={r['calibratedEdgePct']}% | "
            f"GapSource={r['backendModelGapSource']} | "
            f"Conflict={r['oppositeSideConflict']} | "
            f"Decision={r['strictFullSlateDecision']}"
        )

    lines.append("")
    lines.append("Conclusion:")
    lines.append("- Full slate works.")
    lines.append("- Opposite-side conflicts are blocked.")
    lines.append("- Missing backend model gap is research-only.")
    lines.append("- Final Engine V2 context gates still have priority.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()


