from pathlib import Path
import json
import csv
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

POLICY = BASE / "models" / "ASTRODDS_INJURY_IMPACT_POLICY.json"
REPORT = BASE / "reports" / "55_injury_impact_layer_report.txt"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-injury-impact-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-injury-impact-latest.csv"

INPUTS = [
    ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json",
    ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json",
    ROOT / ".astrodds" / "VVS-bullpen-context-latest.json",
    ROOT / ".astrodds" / "VVS-pitcher-context-latest.json",
]

DATASETS = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "astrodss_master_feature_dataset_v2_calibrated.csv",
]

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

def safe_str(x):
    return str(x if x is not None else "")

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

def injury_keys(row):
    return [k for k in row.keys() if "injur" in str(k).lower()]

def collect_rows():
    for path in INPUTS:
        data = read_json(path, None)
        if isinstance(data, list) and data:
            return path, data
    return None, []

def normalize_game(row):
    return row.get("game") or f"{row.get('awayTeam', '')} @ {row.get('homeTeam', '')}".strip()

def classify_injury_risk(row):
    keys = injury_keys(row)
    details = []
    flags = []

    if not keys:
        return {
            "injuryContextStatus": "no_verified_injury_fields",
            "injuryRiskLabel": "unknown",
            "injuryImpactScore": 0,
            "injuryContextFlags": "injury_source_missing",
            "injuryDetails": "No verified injury field was found in the current context row.",
            "officialBuyImpact": "review_if_used_for_strict_production",
        }

    score = 0
    for key in keys:
        value = row.get(key)
        text = safe_str(value).lower()
        if text in ["", "none", "null", "0", "false", "[]", "{}"]:
            continue

        details.append(f"{key}={value}")

        if any(w in text for w in ["out", "injured", "il", "10-day", "15-day", "60-day", "scratch"]):
            score += 50
            flags.append("confirmed_injury_signal")
        elif any(w in text for w in ["questionable", "day-to-day", "dtd", "probable"]):
            score += 25
            flags.append("uncertain_injury_signal")
        else:
            score += 10
            flags.append("injury_data_present")

    if score >= 50:
        label = "high"
        impact = "block_or_admin_review"
    elif score >= 25:
        label = "medium"
        impact = "manual_review"
    elif details:
        label = "low"
        impact = "monitor"
    else:
        label = "none"
        impact = "none"

    return {
        "injuryContextStatus": "available",
        "injuryRiskLabel": label,
        "injuryImpactScore": min(score, 100),
        "injuryContextFlags": "|".join(sorted(set(flags))) if flags else "none",
        "injuryDetails": "; ".join(details) if details else "No active injury signals found in available fields.",
        "officialBuyImpact": impact,
    }

def main():
    generated = datetime.utcnow().isoformat() + "Z"
    input_path, rows = collect_rows()

    dataset_audit = []
    injury_dataset_ready = False

    for dataset in DATASETS:
        cols = csv_columns(dataset)
        count = csv_count(dataset)
        injury_cols = [c for c in cols if "injur" in c.lower()]
        ready = dataset.exists() and count > 0 and bool(injury_cols)
        if ready:
            injury_dataset_ready = True
        dataset_audit.append({
            "file": str(dataset),
            "name": dataset.name,
            "exists": dataset.exists(),
            "rows": count,
            "injuryColumns": injury_cols,
            "ready": ready,
        })

    impact_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        risk = classify_injury_risk(row)

        impact_rows.append({
            "snapshotTime": generated,
            "source": str(input_path) if input_path else "",
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "game": normalize_game(row),
            "awayTeam": row.get("awayTeam"),
            "homeTeam": row.get("homeTeam"),
            "pick": row.get("pick") or row.get("selectedSide"),
            "decision": row.get("finalEngineDecision") or row.get("thresholdDecision") or row.get("decision"),
            "grade": row.get("finalGrade") or row.get("grade"),
            **risk,
            "paperOnly": True,
        })

    write_json(OUT_JSON, impact_rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "snapshotTime", "source", "gameId", "date", "game", "awayTeam", "homeTeam",
        "pick", "decision", "grade", "injuryContextStatus", "injuryRiskLabel",
        "injuryImpactScore", "injuryContextFlags", "injuryDetails",
        "officialBuyImpact", "paperOnly",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in impact_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    policy = {
        "version": "ASTRODDS_INJURY_IMPACT_POLICY_V1",
        "createdAt": generated,
        "status": "READY_WITH_UNKNOWN_SOURCE" if impact_rows else "NO_RUNTIME_ROWS",
        "verifiedInjuryDatasetReady": injury_dataset_ready,
        "rules": {
            "high": "block_or_admin_review_before_official_buy",
            "medium": "manual_review_before_official_buy",
            "low": "monitor_only",
            "none": "no_injury_block",
            "unknown": "do_not_claim_injury_clean; wait for verified source before marketing injury intelligence",
        },
        "currentLimit": "No live verified injury API is connected in this script. It only formalizes detection from available fields and prevents false claims.",
        "outputs": {
            "json": str(OUT_JSON),
            "csv": str(OUT_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    counts = {}
    for r in impact_rows:
        label = r.get("injuryRiskLabel", "unknown")
        counts[label] = counts.get(label, 0) + 1

    lines = []
    lines.append("ASTRODDS 55 INJURY IMPACT LAYER REPORT")
    lines.append("=" * 48)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Input source: {input_path if input_path else 'none'}")
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Output rows: {len(impact_rows)}")
    lines.append(f"Verified injury dataset ready: {injury_dataset_ready}")
    lines.append("")
    lines.append("Risk counts:")
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("Injury dataset audit:")
    for d in dataset_audit:
        lines.append(
            f"- {d['name']} | exists={d['exists']} rows={d['rows']} "
            f"injuryCols={len(d['injuryColumns'])} ready={d['ready']}"
        )
    lines.append("")
    lines.append("Current injury impact rows:")
    for r in impact_rows[:20]:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | Risk={r.get('injuryRiskLabel')} | "
            f"Flags={r.get('injuryContextFlags')} | OfficialBuyImpact={r.get('officialBuyImpact')}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- This layer does not invent injuries.")
    lines.append("- If no verified injury fields exist, it marks injury status as unknown/source missing.")
    lines.append("- Do not market injury intelligence until a verified injury source is connected.")
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: injury impact layer only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

