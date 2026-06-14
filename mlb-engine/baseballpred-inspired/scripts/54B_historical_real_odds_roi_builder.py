from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "54B_historical_real_odds_roi_builder_report.txt"
OUT_JSON = BASE / "reports" / "54B_historical_real_odds_roi_builder.json"

CANDIDATE_FILES = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_dataset_skeleton.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "astrodss_master_feature_dataset_v2_calibrated.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_2016_2026.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "moneyline_historical_predictions.csv",
    ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json",
    ROOT / ".astrodds" / "ASTRODDS-odds-snapshot-ledger.json",
    ROOT / ".astrodds" / "ASTRODDS-clv-line-movement-latest.json",
    ROOT / "public" / "astrodds-proof-log.json",
]

LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"

REAL_ODDS_WORDS = [
    "odds", "moneyline", "american", "decimal", "closing", "close",
    "open", "entry_price", "entryprice", "book", "sportsbook",
    "sportsbook_home_prob", "sportsbook_away_prob"
]
PROB_WORDS = ["probability", "marketprobability", "calibrated", "implied", "price"]
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

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

def csv_columns(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return next(csv.reader(f))
    except Exception:
        return []

def csv_count(path):
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0

def json_columns_and_count(path):
    data = read_json(path, None)
    if isinstance(data, list):
        keys = set()
        for row in data[:50]:
            if isinstance(row, dict):
                keys.update(row.keys())
        return sorted(keys), len(data)
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        keys = set()
        rows = data.get("rows", [])
        for row in rows[:50]:
            if isinstance(row, dict):
                keys.update(row.keys())
        return sorted(keys), len(rows)
    if isinstance(data, dict):
        return sorted(data.keys()), 1
    return [], 0

def hits(columns, words):
    out = []
    for col in columns:
        c = str(col).lower()
        for w in words:
            if w.lower() in c:
                out.append(col)
                break
    return sorted(set(out))

def ledger_forward_summary():
    ledger = read_json(LEDGER, [])
    if not isinstance(ledger, list):
        ledger = []

    wins = [r for r in ledger if str(r.get("result", "")).lower() == "win"]
    losses = [r for r in ledger if str(r.get("result", "")).lower() == "loss"]
    pending = [r for r in ledger if str(r.get("result", "pending")).lower() not in ["win", "loss"]]
    resolved = len(wins) + len(losses)
    win_rate = round((len(wins) / resolved) * 100, 2) if resolved else None

    units = 0.0
    for r in ledger:
        if "paperProfitUnits" in r:
            units += fnum(r.get("paperProfitUnits"))
        elif str(r.get("result", "")).lower() == "win":
            units += 1.0
        elif str(r.get("result", "")).lower() == "loss":
            units -= 1.0

    return {
        "rows": len(ledger),
        "resolved": resolved,
        "wins": len(wins),
        "losses": len(losses),
        "pending": len(pending),
        "winRatePct": win_rate,
        "paperUnits": round(units, 3),
        "status": "FORWARD_PAPER_TRACKING_ONLY",
    }

def main():
    generated = datetime.utcnow().isoformat() + "Z"
    candidates = []

    for path in CANDIDATE_FILES:
        if not path.exists():
            candidates.append({
                "name": path.name,
                "file": str(path),
                "exists": False,
                "rows": 0,
                "status": "MISSING",
            })
            continue

        if path.suffix.lower() == ".csv":
            cols = csv_columns(path)
            rows = csv_count(path)
        else:
            cols, rows = json_columns_and_count(path)

        real_cols = hits(cols, REAL_ODDS_WORDS)
        prob_cols = hits(cols, PROB_WORDS)
        result_cols = hits(cols, RESULT_WORDS)
        pick_cols = hits(cols, PICK_WORDS)
        profit_cols = hits(cols, PROFIT_WORDS)

        has_real_inputs = bool(real_cols and result_cols and pick_cols)
        has_prob_inputs = bool(prob_cols and result_cols and pick_cols)
        has_forward_profit = bool(profit_cols and result_cols)

        if has_real_inputs and rows >= 100:
            status = "REAL_HISTORICAL_ODDS_READY"
        elif has_real_inputs and rows == 0:
            status = "TEMPLATE_ONLY_ZERO_ROWS"
        elif has_real_inputs and rows < 100:
            status = "REAL_ODDS_TOO_FEW_ROWS"
        elif has_prob_inputs:
            status = "PROBABILITY_ONLY_VALIDATION"
        elif has_forward_profit:
            status = "FORWARD_PAPER_TRACKING"
        elif real_cols or prob_cols:
            status = "ODDS_OR_PROB_DATA_INCOMPLETE"
        else:
            status = "NO_ODDS_ROI_INPUTS"

        candidates.append({
            "name": path.name,
            "file": str(path),
            "exists": True,
            "rows": rows,
            "columns": len(cols),
            "status": status,
            "realOddsColumns": real_cols,
            "probabilityColumns": prob_cols,
            "resultColumns": result_cols,
            "pickColumns": pick_cols,
            "profitColumns": profit_cols,
        })

    real_ready = [c for c in candidates if c.get("status") == "REAL_HISTORICAL_ODDS_READY"]
    templates = [c for c in candidates if c.get("status") == "TEMPLATE_ONLY_ZERO_ROWS"]
    probability_only = [c for c in candidates if c.get("status") == "PROBABILITY_ONLY_VALIDATION"]
    forward = ledger_forward_summary()

    if real_ready:
        status = "REAL_HISTORICAL_ODDS_ROI_READY"
        conclusion = "Historical real-odds ROI can be computed from existing data."
        next_step = "Build ROI calculator using the best real odds dataset."
    else:
        status = "REAL_HISTORICAL_ODDS_MISSING"
        conclusion = "No populated historical real odds dataset is available. The previous 54 audit found a skeleton/template, but it has 0 rows."
        next_step = "Use live forward tracking now. Add/import historical odds later before marketing true historical ROI."

    output = {
        "generatedAt": generated,
        "status": status,
        "conclusion": conclusion,
        "nextStep": next_step,
        "realReadyCandidates": real_ready,
        "templateOnlyCandidates": templates,
        "probabilityOnlyCandidates": probability_only,
        "forwardPaperTracking": forward,
        "allCandidates": candidates,
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 54B HISTORICAL REAL ODDS ROI BUILDER REPORT")
    lines.append("=" * 64)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append(f"Conclusion: {conclusion}")
    lines.append(f"Next step: {next_step}")
    lines.append("")
    lines.append("Forward paper tracking:")
    lines.append(f"- Rows: {forward['rows']}")
    lines.append(f"- Resolved: {forward['resolved']}")
    lines.append(f"- Wins: {forward['wins']}")
    lines.append(f"- Losses: {forward['losses']}")
    lines.append(f"- Pending: {forward['pending']}")
    lines.append(f"- Win rate: {forward['winRatePct']}%")
    lines.append(f"- Paper units: {forward['paperUnits']}u")
    lines.append("")
    lines.append("Candidate classification:")
    for c in candidates:
        if not c.get("exists"):
            continue
        lines.append(
            f"- {c['name']} | status={c['status']} | rows={c.get('rows')} | "
            f"realOddsCols={len(c.get('realOddsColumns', []))} "
            f"probCols={len(c.get('probabilityColumns', []))} "
            f"resultCols={len(c.get('resultColumns', []))} "
            f"pickCols={len(c.get('pickColumns', []))}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- Probability/even-money validation is not the same as true historical sportsbook ROI.")
    lines.append("- Current public proof log is valid forward paper tracking.")
    lines.append("- Do not claim real historical ROI until populated odds/closing-line data exists.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append("")
    lines.append("Rule: audit/build guard only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

