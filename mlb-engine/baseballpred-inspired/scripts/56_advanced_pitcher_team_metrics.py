from pathlib import Path
import json
import csv
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

POLICY = BASE / "models" / "ASTRODDS_ADVANCED_PITCHER_TEAM_METRICS_POLICY.json"
REPORT = BASE / "reports" / "56_advanced_pitcher_team_metrics_report.txt"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-advanced-pitcher-team-metrics-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-advanced-pitcher-team-metrics-latest.csv"

INPUTS = [
    ROOT / ".astrodds" / "VVS-pitcher-context-latest.json",
    ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json",
    ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json",
]

DATASETS = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "astrodss_master_feature_dataset_v2_calibrated.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_2016_2026.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
]

ADVANCED_WORDS = [
    "fip", "xfip", "xera", "k_pct", "bb_pct", "kbb", "k_minus_bb",
    "hr9", "barrel", "hardhit", "strikeout", "walk", "whiff",
    "csw", "siera", "stuff", "pitching_plus"
]

TEAM_WORDS = [
    "pyth", "run_diff", "recent10", "rest_days", "home_win_pct",
    "away_win_pct", "team_win", "runs_for", "runs_against"
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

def fnum(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

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

def find_cols(cols, words):
    hits = []
    for c in cols:
        low = str(c).lower()
        if any(w in low for w in words):
            hits.append(c)
    return sorted(set(hits))

def collect_rows():
    for path in INPUTS:
        data = read_json(path, None)
        if isinstance(data, list) and data:
            return path, data
    return None, []

def get(row, *keys):
    for key in keys:
        if key in row and row.get(key) not in [None, ""]:
            return row.get(key)
    return None

def pitcher_side_metrics(row, side):
    prefix = f"{side}Pitcher_"

    era = fnum(get(row, f"{prefix}era", f"{side}_pitcher_era", f"{side}PitcherEra"))
    whip = fnum(get(row, f"{prefix}whip", f"{side}_pitcher_whip", f"{side}PitcherWhip"))
    innings = fnum(get(row, f"{prefix}inningsPitched"))
    strikeouts = fnum(get(row, f"{prefix}strikeOuts"))
    walks = fnum(get(row, f"{prefix}baseOnBalls"))
    hrs = fnum(get(row, f"{prefix}homeRuns"))
    starts = fnum(get(row, f"{prefix}gamesStarted"))

    flags = []
    score = 50

    if era is None or whip is None:
        flags.append("starter_core_stats_missing")
        return {
            "era": era,
            "whip": whip,
            "innings": innings,
            "starts": starts,
            "kbb": None,
            "hr9": None,
            "qualityScore": 0,
            "qualityLabel": "unknown",
            "flags": "|".join(flags),
        }

    # Simple deterministic diagnostic score, not a betting model.
    if era <= 3.25:
        score += 18
    elif era <= 4.25:
        score += 8
    elif era >= 5.00:
        score -= 20
        flags.append("high_era")
    elif era >= 4.50:
        score -= 10
        flags.append("medium_high_era")

    if whip <= 1.15:
        score += 18
    elif whip <= 1.30:
        score += 8
    elif whip >= 1.45:
        score -= 20
        flags.append("high_whip")
    elif whip >= 1.35:
        score -= 10
        flags.append("medium_high_whip")

    kbb = None
    if strikeouts is not None and walks is not None:
        kbb = round(strikeouts / max(walks, 1), 2)
        if kbb >= 3.5:
            score += 10
        elif kbb < 2.0:
            score -= 8
            flags.append("low_kbb")

    hr9 = None
    if hrs is not None and innings and innings > 0:
        hr9 = round((hrs * 9) / innings, 2)
        if hr9 >= 1.4:
            score -= 8
            flags.append("high_hr9")

    if starts is not None and starts < 3:
        score -= 8
        flags.append("small_starter_sample")

    score = max(0, min(100, score))

    if score >= 70:
        label = "strong"
    elif score >= 55:
        label = "solid"
    elif score >= 40:
        label = "weak"
    else:
        label = "high_risk"

    return {
        "era": era,
        "whip": whip,
        "innings": innings,
        "starts": starts,
        "kbb": kbb,
        "hr9": hr9,
        "qualityScore": score,
        "qualityLabel": label,
        "flags": "|".join(flags) if flags else "none",
    }

def advantage_label(picked, opponent):
    if picked["qualityLabel"] == "unknown" or opponent["qualityLabel"] == "unknown":
        return "unknown"

    diff = picked["qualityScore"] - opponent["qualityScore"]
    if diff >= 15:
        return "pitcher_advantage"
    if diff <= -15:
        return "pitcher_disadvantage"
    return "neutral"

def main():
    generated = datetime.utcnow().isoformat() + "Z"

    dataset_audit = []
    has_advanced_dataset = False
    has_team_dataset = False

    for dataset in DATASETS:
        cols = csv_columns(dataset)
        count = csv_count(dataset)
        advanced_cols = find_cols(cols, ADVANCED_WORDS)
        team_cols = find_cols(cols, TEAM_WORDS)
        if dataset.exists() and count > 0 and advanced_cols:
            has_advanced_dataset = True
        if dataset.exists() and count > 0 and team_cols:
            has_team_dataset = True
        dataset_audit.append({
            "file": str(dataset),
            "name": dataset.name,
            "exists": dataset.exists(),
            "rows": count,
            "advancedPitcherColumns": advanced_cols[:50],
            "teamContextColumns": team_cols[:50],
            "advancedReady": dataset.exists() and count > 0 and bool(advanced_cols),
            "teamContextReady": dataset.exists() and count > 0 and bool(team_cols),
        })

    input_path, rows = collect_rows()
    output_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        pick = row.get("pick") or row.get("selectedSide")
        away = row.get("awayTeam")
        home = row.get("homeTeam")

        away_m = pitcher_side_metrics(row, "away")
        home_m = pitcher_side_metrics(row, "home")

        if pick == away:
            picked_m = away_m
            opp_m = home_m
        elif pick == home:
            picked_m = home_m
            opp_m = away_m
        else:
            picked_m = {"qualityLabel": "unknown", "qualityScore": 0}
            opp_m = {"qualityLabel": "unknown", "qualityScore": 0}

        adv = advantage_label(picked_m, opp_m)
        flags = []

        if adv == "pitcher_disadvantage":
            flags.append("picked_pitcher_disadvantage")
        if picked_m.get("qualityLabel") in ["weak", "high_risk"]:
            flags.append("picked_pitcher_quality_risk")
        if picked_m.get("qualityLabel") == "unknown":
            flags.append("picked_pitcher_advanced_unknown")

        output_rows.append({
            "snapshotTime": generated,
            "source": str(input_path) if input_path else "",
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "game": row.get("game") or f"{away} @ {home}",
            "awayTeam": away,
            "homeTeam": home,
            "pick": pick,
            "decision": row.get("finalEngineDecision") or row.get("thresholdDecision") or row.get("decision"),
            "grade": row.get("finalGrade") or row.get("grade"),
            "awayPitcherQualityScore": away_m["qualityScore"],
            "awayPitcherQualityLabel": away_m["qualityLabel"],
            "awayPitcherAdvancedFlags": away_m["flags"],
            "awayPitcherKBB": away_m["kbb"],
            "awayPitcherHR9": away_m["hr9"],
            "homePitcherQualityScore": home_m["qualityScore"],
            "homePitcherQualityLabel": home_m["qualityLabel"],
            "homePitcherAdvancedFlags": home_m["flags"],
            "homePitcherKBB": home_m["kbb"],
            "homePitcherHR9": home_m["hr9"],
            "pickedPitcherAdvantage": adv,
            "advancedMetricStatus": "derived_from_available_era_whip_kbb_hr9" if input_path else "missing_runtime_context",
            "advancedMetricFlags": "|".join(flags) if flags else "none",
            "officialBuyImpact": "manual_review" if flags else "no_block",
            "paperOnly": True,
        })

    write_json(OUT_JSON, output_rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "snapshotTime", "source", "gameId", "date", "game", "awayTeam", "homeTeam",
        "pick", "decision", "grade", "awayPitcherQualityScore", "awayPitcherQualityLabel",
        "awayPitcherAdvancedFlags", "awayPitcherKBB", "awayPitcherHR9",
        "homePitcherQualityScore", "homePitcherQualityLabel", "homePitcherAdvancedFlags",
        "homePitcherKBB", "homePitcherHR9", "pickedPitcherAdvantage",
        "advancedMetricStatus", "advancedMetricFlags", "officialBuyImpact", "paperOnly",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in output_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    policy = {
        "version": "ASTRODDS_ADVANCED_PITCHER_TEAM_METRICS_POLICY_V1",
        "createdAt": generated,
        "status": "DERIVED_RUNTIME_READY" if output_rows else "NO_RUNTIME_ROWS",
        "advancedPitcherDatasetReady": has_advanced_dataset,
        "teamContextDatasetReady": has_team_dataset,
        "currentLimit": "Uses available pitcher context to derive K/BB and HR/9 when available. True xERA/FIP/xFIP requires an external/statcast-grade source.",
        "rules": {
            "picked_pitcher_disadvantage": "manual_review_before_official_buy",
            "picked_pitcher_quality_risk": "manual_review_before_official_buy",
            "picked_pitcher_advanced_unknown": "do_not_claim_advanced_pitcher_clean",
        },
        "outputs": {
            "json": str(OUT_JSON),
            "csv": str(OUT_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    counts = {}
    for r in output_rows:
        adv = r.get("pickedPitcherAdvantage", "unknown")
        counts[adv] = counts.get(adv, 0) + 1

    lines = []
    lines.append("ASTRODDS 56 ADVANCED PITCHER / TEAM METRICS REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Input source: {input_path if input_path else 'none'}")
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Output rows: {len(output_rows)}")
    lines.append(f"Advanced pitcher dataset ready: {has_advanced_dataset}")
    lines.append(f"Team context dataset ready: {has_team_dataset}")
    lines.append("")
    lines.append("Picked pitcher advantage counts:")
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("Dataset audit:")
    for d in dataset_audit:
        lines.append(
            f"- {d['name']} | exists={d['exists']} rows={d['rows']} "
            f"advancedCols={len(d['advancedPitcherColumns'])} teamCols={len(d['teamContextColumns'])} "
            f"advancedReady={d['advancedReady']} teamReady={d['teamContextReady']}"
        )
    lines.append("")
    lines.append("Current derived rows:")
    for r in output_rows[:20]:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | Advantage={r.get('pickedPitcherAdvantage')} | "
            f"Away={r.get('awayPitcherQualityLabel')}({r.get('awayPitcherQualityScore')}) "
            f"Home={r.get('homePitcherQualityLabel')}({r.get('homePitcherQualityScore')}) | "
            f"Flags={r.get('advancedMetricFlags')}"
        )
    lines.append("")
    lines.append("Important:")
    lines.append("- This layer derives extra pitcher diagnostics from available runtime pitcher stats.")
    lines.append("- True advanced metrics like xERA/FIP/xFIP require a verified external/statcast-grade data source.")
    lines.append("- Do not market xERA/FIP/xFIP until those columns/sources are actually connected.")
    lines.append("")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append(f"Output JSON: {OUT_JSON}")
    lines.append(f"Output CSV: {OUT_CSV}")
    lines.append("")
    lines.append("Rule: advanced metrics layer only. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

