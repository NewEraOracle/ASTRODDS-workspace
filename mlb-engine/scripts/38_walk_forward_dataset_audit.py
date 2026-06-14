from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[2]
REPORT = WORKSPACE / "mlb-engine" / "baseballpred-inspired" / "reports" / "38_walk_forward_dataset_audit_report.txt"

CANDIDATES = [
    WORKSPACE / "mlb-engine" / "data" / "processed" / "mlb_moneyline_features_2016_2026.csv",
    WORKSPACE / "mlb-engine" / "data" / "processed" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    WORKSPACE / "mlb-engine" / "data" / "processed" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    WORKSPACE / "mlb-engine" / "data" / "processed" / "moneyline_historical_predictions.csv",
    WORKSPACE / "mlb-engine" / "baseballpred-inspired" / "data" / "processed" / "astrodss_master_feature_dataset_v2_calibrated.csv",
]

def detect_year(row):
    for key in ["season", "year", "game_year"]:
        if key in row and str(row.get(key, "")).strip():
            try:
                return int(float(row[key]))
            except Exception:
                pass

    for key in ["date", "game_date", "gameDate", "commence_time"]:
        value = str(row.get(key, "")).strip()
        if len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])

    return None

def audit_csv(path):
    if not path.exists():
        return {"path": str(path), "exists": False}

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)

    years = {}
    for row in rows:
        y = detect_year(row)
        if y:
            years[y] = years.get(y, 0) + 1

    winner_cols = [c for c in columns if "winner" in c.lower() or "result" in c.lower() or "home_win" in c.lower()]
    odds_cols = [c for c in columns if "odds" in c.lower() or "prob" in c.lower() or "price" in c.lower() or "line" in c.lower()]
    team_cols = [c for c in columns if "team" in c.lower() or c.lower() in ["home", "away"]]

    score = 0
    if rows:
        score += 2
    if years:
        score += 2
    if min(years.keys(), default=9999) <= 2016 and max(years.keys(), default=0) >= 2025:
        score += 3
    if winner_cols:
        score += 3
    if odds_cols:
        score += 2
    if team_cols:
        score += 1

    return {
        "path": str(path),
        "exists": True,
        "rows": len(rows),
        "columnsCount": len(columns),
        "years": dict(sorted(years.items())),
        "winnerColumns": winner_cols[:12],
        "oddsProbabilityColumns": odds_cols[:20],
        "teamColumns": team_cols[:20],
        "firstColumns": columns[:30],
        "score": score,
    }

def main():
    audits = [audit_csv(p) for p in CANDIDATES]
    ranked = sorted(audits, key=lambda x: x.get("score", 0), reverse=True)

    lines = []
    lines.append("ASTRODDS 38 WALK-FORWARD DATASET AUDIT")
    lines.append("=" * 48)
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("Candidate datasets:")

    for a in ranked:
        lines.append("")
        lines.append(f"- {Path(a['path']).name}")
        lines.append(f"  Exists: {a.get('exists')}")
        lines.append(f"  Score: {a.get('score', 0)}")
        lines.append(f"  Rows: {a.get('rows', 0)}")
        lines.append(f"  Columns: {a.get('columnsCount', 0)}")
        lines.append(f"  Years: {a.get('years', {})}")
        lines.append(f"  Winner/result cols: {a.get('winnerColumns', [])}")
        lines.append(f"  Odds/prob cols: {a.get('oddsProbabilityColumns', [])}")
        lines.append(f"  Team cols: {a.get('teamColumns', [])}")

    best = ranked[0] if ranked else {}
    lines.append("")
    lines.append("Recommendation:")
    if best.get("exists") and best.get("rows", 0) > 0:
        lines.append(f"- Best candidate: {Path(best['path']).name}")
        lines.append("- Next step: build 39_walk_forward_backtest.py using this dataset.")
    else:
        lines.append("- No usable dataset found yet. Need rebuild historical features first.")

    lines.append("")
    lines.append("Rule: audit only. No model changes. No betting automation.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
