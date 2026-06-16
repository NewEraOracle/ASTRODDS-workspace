from pathlib import Path
from datetime import datetime
import csv, json, math

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "190_moneyline_historical_calibration_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-historical-calibration-latest.json"

SOURCE = PROCESSED / "mlb_moneyline_features.csv"

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        return list(csv.DictReader(f))

def fnum(v, default=None):
    try:
        s = str(v).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def find_prob(row):
    candidates = ["calibratedProbabilityV2","modelProbability","home_win_probability","probability","pred_prob","homeProb"]
    for c in candidates:
        if c in row:
            v = fnum(row.get(c), None)
            if v is not None:
                if v > 1: v /= 100.0
                return max(0.001, min(0.999, v)), c
    # fallback: use home_win_pct_before if present. not model, but useful sanity.
    for c in ["home_win_pct_before","homeWinPctBefore"]:
        if c in row:
            v = fnum(row.get(c), None)
            if v is not None:
                return max(0.001, min(0.999, v)), c
    return None, None

def target(row):
    for c in ["target_home_win","home_win","homeWon"]:
        if c in row:
            v = str(row.get(c,"")).strip().lower()
            if v in ("1","true","yes","win"):
                return 1
            if v in ("0","false","no","loss"):
                return 0
    if "winner" in row and "home_team" in row:
        return 1 if str(row.get("winner")).strip().lower() == str(row.get("home_team")).strip().lower() else 0
    return None

def bucket(p):
    lo = math.floor(p*10)/10
    hi = lo + 0.099
    return f"{lo:.1f}-{hi:.1f}"

def brier(rows):
    if not rows:
        return 0
    return sum((r["p"]-r["y"])**2 for r in rows)/len(rows)

def logloss(rows):
    if not rows:
        return 0
    return -sum(r["y"]*math.log(r["p"]) + (1-r["y"])*math.log(1-r["p"]) for r in rows)/len(rows)

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    raw = read_csv(SOURCE)
    parsed = []
    prob_col = None
    for r in raw:
        p, col = find_prob(r)
        y = target(r)
        if p is None or y is None:
            continue
        prob_col = prob_col or col
        parsed.append({"p": p, "y": y, "season": r.get("season",""), "date": r.get("game_date", r.get("date",""))})

    buckets = {}
    for r in parsed:
        buckets.setdefault(bucket(r["p"]), []).append(r)

    bucket_rows = []
    for b, rs in sorted(buckets.items()):
        n = len(rs)
        avg_p = sum(r["p"] for r in rs)/n
        hit = sum(r["y"] for r in rs)/n
        bucket_rows.append({
            "bucket": b,
            "n": n,
            "avgPred": round(avg_p,4),
            "homeWinRate": round(hit,4),
            "calibrationGap": round(hit-avg_p,4),
            "brier": round(brier(rs),4),
        })

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "source": str(SOURCE),
        "rowsRaw": len(raw),
        "rowsUsed": len(parsed),
        "probabilityColumn": prob_col,
        "overall": {
            "brier": round(brier(parsed),4),
            "logLoss": round(logloss(parsed),4),
            "baseRate": round(sum(r["y"] for r in parsed)/len(parsed),4) if parsed else 0,
        },
        "buckets": bucket_rows,
        "decision": "Calibration audit only. Do not change live thresholds automatically.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 190 MONEYLINE HISTORICAL CALIBRATION AUDIT",
        "=" * 74,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Source: {SOURCE}",
        f"Rows raw: {len(raw)}",
        f"Rows used: {len(parsed)}",
        f"Probability column used: {prob_col}",
        "",
        "Overall:",
        f"- Brier: {out['overall']['brier']}",
        f"- LogLoss: {out['overall']['logLoss']}",
        f"- Base rate: {out['overall']['baseRate']}",
        "",
        "Buckets:",
    ]
    for b in bucket_rows:
        lines.append(f"- {b['bucket']} | n={b['n']} | avgPred={b['avgPred']} | homeWinRate={b['homeWinRate']} | gap={b['calibrationGap']} | brier={b['brier']}")
    lines += ["", "Decision:", "- Use as sanity check. Live Moneyline remains 135 until live sample is enough.", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
