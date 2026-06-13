from pathlib import Path
import csv
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"
CALIBRATION = ROOT / "models" / "ASTRODDS_MLB_CALIBRATION_V2.json"

OUT_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-full-slate-engine-latest.json"
OUT_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-full-slate-engine-latest.csv"
REPORT = ROOT / "reports" / "25_full_slate_engine_report.txt"

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))

def read_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def bucket_from_gap_pct(gap_pct):
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

def model_gap_pct(raw_prob):
    p = fnum(raw_prob)
    if p is None:
        return None
    return round(abs(p - 0.5) * 200, 2)

def classify(edge):
    e = fnum(edge)
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
        data = fetch_json(API_URL)
    except Exception as e:
        msg = (
            "ASTRODDS 25 FULL SLATE ENGINE REPORT\n"
            "=====================================\n\n"
            f"FAILED: Could not reach local API: {API_URL}\n"
            f"Error: {e}\n\n"
            "Fix:\n"
            "Run your Next.js dev server first:\n"
            "npm run dev\n"
        )
        REPORT.write_text(msg, encoding="utf-8")
        print(msg)
        return

    calibration = read_json(CALIBRATION, {})
    buckets = calibration.get("calibrationBuckets", {})
    global_prob = fnum(calibration.get("globalTrainProbability")) or 0.5652

    rows = data.get("bestBetRows") or data.get("rows") or []
    candidates = []

    for r in rows:
        market_type = r.get("marketType")
        away = r.get("awayTeam")
        home = r.get("homeTeam")
        pick = r.get("selectedSide") or r.get("pick")

        if market_type != "moneyline":
            continue

        if pick not in [away, home]:
            continue

        market = fnum(r.get("marketProbability"))
        raw_model = fnum(r.get("calibratedProbability") or r.get("modelProbability"))

        if market is None or raw_model is None:
            continue

        if market < 0.30 or market > 0.75:
            continue

        gap_pct = fnum(r.get("modelProbabilityGapPct") or r.get("modelGapPct"))
        if gap_pct is None:
            gap_pct = model_gap_pct(raw_model)

        bucket = bucket_from_gap_pct(gap_pct)
        cal_prob = fnum(buckets.get(bucket, {}).get("probability")) or global_prob

        raw_edge = (raw_model - market) * 100
        cal_edge = (cal_prob - market) * 100

        decision = classify(cal_edge)

        candidates.append({
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "gameId": r.get("gameId"),
            "date": r.get("date"),
            "game": f"{away} @ {home}",
            "awayTeam": away,
            "homeTeam": home,
            "pick": pick,
            "status": r.get("status"),
            "marketType": market_type,
            "marketProbability": round(market, 6),
            "rawModelProbability": round(raw_model, 6),
            "modelGapPct": gap_pct,
            "calibrationBucket": bucket,
            "calibratedProbabilityV2": round(cal_prob, 6),
            "rawEdgePct": round(raw_edge, 2),
            "calibratedEdgePct": round(cal_edge, 2),
            "fullSlateDecision": decision,
            "confidence": r.get("matchConfidence"),
            "risk": r.get("riskLevel"),
            "reason": r.get("mainReason"),
            "paperOnly": True,
        })

    # keep best candidate per game
    best_by_game = {}
    for c in candidates:
        gid = c.get("gameId") or c.get("game")
        old = best_by_game.get(gid)
        if not old or c["calibratedEdgePct"] > old["calibratedEdgePct"]:
            best_by_game[gid] = c

    final_rows = list(best_by_game.values())
    final_rows.sort(key=lambda x: x["calibratedEdgePct"], reverse=True)

    OUT_JSON.write_text(json.dumps(final_rows, indent=2), encoding="utf-8")

    fields = sorted({k for r in final_rows for k in r.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(final_rows)

    counts = {}
    for r in final_rows:
        d = r["fullSlateDecision"]
        counts[d] = counts.get(d, 0) + 1

    lines = []
    lines.append("ASTRODDS 25 FULL SLATE ENGINE REPORT")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Goal:")
    lines.append("Score the full MLB moneyline slate from backend rows using calibrated probability.")
    lines.append("")
    lines.append(f"Backend rows: {len(rows)}")
    lines.append(f"Moneyline candidates: {len(candidates)}")
    lines.append(f"Best per game rows: {len(final_rows)}")
    lines.append("")
    lines.append("Decision counts:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Full slate ranked:")
    for r in final_rows:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Market={round(r['marketProbability']*100,2)}% | "
            f"Raw={round(r['rawModelProbability']*100,2)}% | "
            f"Cal={round(r['calibratedProbabilityV2']*100,2)}% | "
            f"CalEdge={r['calibratedEdgePct']}% | "
            f"Decision={r['fullSlateDecision']}"
        )

    lines.append("")
    lines.append("Important:")
    lines.append("- This is full slate research output.")
    lines.append("- It does not override final Engine V2 context gates yet.")
    lines.append("- Next: connect full slate rows to context gates and final decision rules.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"CSV: {OUT_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
