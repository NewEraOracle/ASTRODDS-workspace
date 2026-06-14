from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "54_historical_odds_roi_audit_report.txt"
OUT_JSON = BASE / "reports" / "54_historical_odds_roi_audit.json"

SEARCH_DIRS = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data",
    ROOT / "mlb-engine" / "data",
    ROOT / ".astrodds",
    ROOT / "public",
]

IMPORTANT_FILES = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "astrodss_master_feature_dataset_v2_calibrated.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_2016_2026.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json",
    ROOT / ".astrodds" / "ASTRODDS-clv-line-movement-latest.json",
    ROOT / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.json",
    ROOT / "public" / "astrodds-proof-log.json",
]

ODDS_WORDS = [
    "odds", "price", "market", "moneyline", "american", "decimal",
    "implied", "probability", "closing", "close", "open", "entry",
    "clv", "line"
]
REAL_ODDS_WORDS = [
    "odds", "moneyline", "american", "decimal", "closing", "close",
    "open", "entry_price", "entryprice", "book", "sportsbook"
]
RESULT_WORDS = ["winner", "result", "home_win", "target_home_win", "model_correct"]
PICK_WORDS = ["pick", "model_pick", "predicted", "side", "selected"]
PROFIT_WORDS = ["profit", "units", "roi", "paperprofit"]

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def safe_lower(x):
    return str(x or "").lower()

def csv_columns(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            return next(reader)
    except Exception:
        return []

def csv_sample_rows(path, limit=5):
    rows = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if len(rows) >= limit:
                    break
    except Exception:
        return []
    return rows

def csv_row_count(path):
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0

def json_columns(data):
    if isinstance(data, list) and data:
        keys = set()
        for row in data[:25]:
            if isinstance(row, dict):
                keys.update(row.keys())
        return sorted(keys)
    if isinstance(data, dict):
        if isinstance(data.get("rows"), list):
            keys = set()
            for row in data.get("rows", [])[:25]:
                if isinstance(row, dict):
                    keys.update(row.keys())
            return sorted(keys)
        return sorted(data.keys())
    return []

def json_row_count(data):
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return len(data.get("rows"))
    return 1 if isinstance(data, dict) else 0

def has_any(cols, words):
    low = [safe_lower(c) for c in cols]
    hits = []
    for c in low:
        for w in words:
            if w in c:
                hits.append(c)
                break
    return sorted(set(hits))

def score_candidate(cols, rows):
    odds_cols = has_any(cols, ODDS_WORDS)
    real_odds_cols = has_any(cols, REAL_ODDS_WORDS)
    result_cols = has_any(cols, RESULT_WORDS)
    pick_cols = has_any(cols, PICK_WORDS)
    profit_cols = has_any(cols, PROFIT_WORDS)

    score = 0
    if rows > 1000:
        score += 2
    if rows > 20000:
        score += 2
    if odds_cols:
        score += 2
    if real_odds_cols:
        score += 4
    if result_cols:
        score += 3
    if pick_cols:
        score += 2
    if profit_cols:
        score += 2

    return score, odds_cols, real_odds_cols, result_cols, pick_cols, profit_cols

def find_files():
    found = []
    for p in IMPORTANT_FILES:
        if p.exists():
            found.append(p)

    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        for ext in ["*.csv", "*.json"]:
            for p in d.rglob(ext):
                name = p.name.lower()
                if any(w in name for w in ODDS_WORDS + ["ledger", "proof", "feature"]):
                    found.append(p)

    unique = []
    seen = set()
    for p in found:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return unique

def main():
    generated = datetime.utcnow().isoformat() + "Z"
    candidates = []

    for path in find_files():
        suffix = path.suffix.lower()
        cols = []
        rows = 0

        if suffix == ".csv":
            cols = csv_columns(path)
            rows = csv_row_count(path)
        elif suffix == ".json":
            data = read_json(path, None)
            cols = json_columns(data)
            rows = json_row_count(data)
        else:
            continue

        score, odds_cols, real_odds_cols, result_cols, pick_cols, profit_cols = score_candidate(cols, rows)

        has_real_roi_inputs = bool(real_odds_cols and result_cols and pick_cols)
        has_current_profit_tracking = bool(profit_cols and result_cols)

        status = "NOT_ODDS_ROI"
        if has_real_roi_inputs:
            status = "REAL_ODDS_ROI_POSSIBLE"
        elif odds_cols and result_cols and pick_cols:
            status = "PROBABILITY_ONLY_ROI_POSSIBLE"
        elif has_current_profit_tracking:
            status = "CURRENT_PAPER_TRACKING_ONLY"
        elif odds_cols:
            status = "ODDS_DATA_PRESENT_BUT_INCOMPLETE"

        candidates.append({
            "file": str(path),
            "name": path.name,
            "suffix": suffix,
            "rows": rows,
            "columns": len(cols),
            "score": score,
            "status": status,
            "oddsColumns": odds_cols[:25],
            "realOddsColumns": real_odds_cols[:25],
            "resultColumns": result_cols[:25],
            "pickColumns": pick_cols[:25],
            "profitColumns": profit_cols[:25],
            "hasRealRoiInputs": has_real_roi_inputs,
            "hasCurrentProfitTracking": has_current_profit_tracking,
        })

    candidates.sort(key=lambda x: (x["score"], x["rows"]), reverse=True)

    real_roi_candidates = [c for c in candidates if c["status"] == "REAL_ODDS_ROI_POSSIBLE"]
    probability_only = [c for c in candidates if c["status"] == "PROBABILITY_ONLY_ROI_POSSIBLE"]
    current_tracking = [c for c in candidates if c["status"] == "CURRENT_PAPER_TRACKING_ONLY"]

    if real_roi_candidates:
        overall_status = "REAL_ODDS_ROI_READY_TO_BUILD"
        recommendation = "Build 54B historical real-odds ROI using the best real-odds candidate."
    elif probability_only:
        overall_status = "NO_REAL_ODDS_BUT_PROBABILITY_ROI_AVAILABLE"
        recommendation = "Current historical datasets support win/loss and probability/even-money validation, but not real sportsbook ROI."
    elif current_tracking:
        overall_status = "CURRENT_PAPER_TRACKING_ONLY"
        recommendation = "Live ledger tracks units/profit, but historical real odds are not available yet."
    else:
        overall_status = "MISSING_HISTORICAL_ODDS"
        recommendation = "Add historical odds/closing line source before claiming real ROI."

    output = {
        "generatedAt": generated,
        "status": overall_status,
        "recommendation": recommendation,
        "realRoiCandidates": real_roi_candidates,
        "probabilityOnlyCandidates": probability_only,
        "currentTrackingCandidates": current_tracking,
        "allCandidates": candidates,
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 54 HISTORICAL ODDS ROI AUDIT")
    lines.append("=" * 48)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {overall_status}")
    lines.append(f"Recommendation: {recommendation}")
    lines.append("")
    lines.append("Top candidates:")
    for c in candidates[:10]:
        lines.append(
            f"- {c['name']} | status={c['status']} | score={c['score']} | rows={c['rows']} | "
            f"realOddsCols={len(c['realOddsColumns'])} resultCols={len(c['resultColumns'])} pickCols={len(c['pickColumns'])}"
        )
        if c["realOddsColumns"]:
            lines.append(f"  real odds cols: {', '.join(c['realOddsColumns'][:8])}")
        elif c["oddsColumns"]:
            lines.append(f"  odds/prob cols: {', '.join(c['oddsColumns'][:8])}")
    lines.append("")
    lines.append("Interpretation:")
    if overall_status == "REAL_ODDS_ROI_READY_TO_BUILD":
        lines.append("- At least one dataset appears to contain odds + results + picks.")
        lines.append("- Next: compute true ROI using entry/closing prices.")
    elif overall_status == "NO_REAL_ODDS_BUT_PROBABILITY_ROI_AVAILABLE":
        lines.append("- Historical model validation exists, but it is probability/even-money style.")
        lines.append("- Do not market this as real sportsbook ROI yet.")
    elif overall_status == "CURRENT_PAPER_TRACKING_ONLY":
        lines.append("- Current proof ledger has paper units, but historical odds are not available.")
        lines.append("- Continue logging live entries for real forward ROI.")
    else:
        lines.append("- No complete historical odds dataset was found.")
        lines.append("- Need odds provider export or saved daily market snapshots before real historical ROI.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append("")
    lines.append("Rule: audit only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

