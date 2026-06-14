from pathlib import Path
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "52_baseballpred_feature_parity_audit_report.txt"
OUT_JSON = BASE / "reports" / "52_baseballpred_feature_parity_audit.json"

CANDIDATE_DATASETS = [
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "astrodss_master_feature_dataset_v2_calibrated.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_2016_2026.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ROOT / "mlb-engine" / "baseballpred-inspired" / "data" / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
]

FILES = {
    "calibration_rules": BASE / "models" / "ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json",
    "final_decision": BASE / "scripts" / "17_engine_final_decision.py",
    "full_slate_engine": BASE / "scripts" / "25_full_slate_engine.py",
    "strict_gate": BASE / "scripts" / "26_full_slate_strict_gate.py",
    "public_proof_log": BASE / "scripts" / "29_public_proof_log.py",
    "telegram_public": BASE / "scripts" / "30_telegram_final_engine_alerts.py",
    "runner": BASE / "scripts" / "31_auto_daily_engine_runner.ps1",
    "health_check": BASE / "scripts" / "45_astrodds_health_check.ps1",
    "credit_guard": BASE / "scripts" / "48_credit_guard.py",
    "threshold_context_gate": ROOT / "mlb-engine" / "scripts" / "42_threshold_context_gate.py",
}

RUNTIME = {
    "vvs_final": ROOT / ".astrodds" / "VVS-clean-final-latest.json",
    "engine_final": ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json",
    "ledger": ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json",
    "full_slate_threshold": ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json",
    "proof_html": ROOT / "public" / "astrodds-proof-log.html",
    "proof_json": ROOT / "public" / "astrodds-proof-log.json",
}

def read_text(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def csv_columns(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            return next(reader)
    except Exception:
        return []

def csv_row_count(path):
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0

def has_any(cols, words):
    low = [c.lower() for c in cols]
    return any(any(w in c for w in words) for c in low)

def status(ok, partial=False):
    if ok and not partial:
        return "OK"
    if ok and partial:
        return "PARTIAL"
    return "MISSING"

def main():
    dataset_audit = []
    best_dataset = None
    best_score = -1

    for path in CANDIDATE_DATASETS:
        cols = csv_columns(path)
        rows = csv_row_count(path)

        checks = {
            "exists": path.exists(),
            "rows": rows,
            "columns": len(cols),
            "has_result": has_any(cols, ["winner", "home_win", "target_home_win"]),
            "has_calibration": has_any(cols, ["calibrated", "model_score", "model_pick"]),
            "has_pitcher": has_any(cols, ["pitcher", "probable"]),
            "has_bullpen": has_any(cols, ["bullpen", "reliever"]),
            "has_weather": has_any(cols, ["weather", "wind", "temperature", "precip"]),
            "has_lineup": has_any(cols, ["lineup"]),
            "has_injuries": has_any(cols, ["injury", "injuries", "injured"]),
            "has_odds": has_any(cols, ["odds", "price", "market", "moneyline", "closing", "open"]),
            "has_advanced_pitcher": has_any(cols, ["fip", "xfip", "xera", "k_pct", "bb_pct", "hr9", "strikeout", "walk"]),
        }

        score = 0
        for v in checks.values():
            if isinstance(v, bool) and v:
                score += 1
        if rows > 1000:
            score += 2
        if rows > 20000:
            score += 2

        row = {
            "file": str(path),
            "name": path.name,
            "score": score,
            **checks,
        }
        dataset_audit.append(row)

        if score > best_score:
            best_score = score
            best_dataset = row

    script_text = {name: read_text(path) for name, path in FILES.items()}

    pitcher_script = BASE / "scripts" / "09_pitcher_context_snapshot.py"
    bullpen_script = BASE / "scripts" / "10_bullpen_fatigue_snapshot.py"
    game_context_script = BASE / "scripts" / "08_game_context_snapshot.py"

    feature_status = {
        "calibration": status(
            FILES["calibration_rules"].exists()
            and "engineBuyStrictCalibratedProbability" in read_text(FILES["calibration_rules"])
        ),
        "walk_forward_oos_validation": status(
            (BASE / "reports" / "39_walk_forward_backtest_report.txt").exists()
            and (BASE / "reports" / "40_oos_threshold_validation_report.txt").exists()
        ),
        "threshold_official_buy_rules": status(
            "officialBuyThresholdPassed" in script_text["final_decision"]
            and "locked_engine_buy_min" in script_text["final_decision"]
        ),
        "full_slate_engine": status(
            FILES["full_slate_engine"].exists()
            and FILES["strict_gate"].exists()
            and FILES["threshold_context_gate"].exists()
        ),
        "pitcher_context": status(pitcher_script.exists(), partial=True),
        "bullpen_context": status(bullpen_script.exists()),
        "weather_context": status("open_meteo" in read_text(game_context_script)),
        "lineup_context": status("lineup" in read_text(game_context_script).lower(), partial=True),
        "injuries_context": status(
            bool(best_dataset and best_dataset.get("has_injuries")),
            partial=bool(best_dataset and best_dataset.get("has_injuries"))
        ),
        "advanced_pitcher_metrics": status(
            bool(best_dataset and best_dataset.get("has_advanced_pitcher")),
            partial=bool(best_dataset and best_dataset.get("has_advanced_pitcher"))
        ),
        "historical_real_odds_roi": status(
            bool(best_dataset and best_dataset.get("has_odds")),
            partial=bool(best_dataset and best_dataset.get("has_odds"))
        ),
        "public_proof_log": status(
            FILES["public_proof_log"].exists()
            and RUNTIME["proof_html"].exists()
            and RUNTIME["proof_json"].exists()
        ),
        "telegram_public_client_filter": status(
            "finalEngineDecision" in script_text["telegram_public"]
            and "ENGINE_BUY" in script_text["telegram_public"]
            and "Entry max" in script_text["telegram_public"]
            and "5% bankroll" in script_text["telegram_public"]
        ),
        "credit_guard": status(
            FILES["credit_guard"].exists()
            and "Credit guard" in script_text["health_check"]
            and "48_credit_guard.py" in script_text["runner"]
        ),
        "single_official_source": "NEEDS_REVIEW",
    }

    runtime_counts = {}
    for name, path in RUNTIME.items():
        if path.suffix == ".json":
            data = read_json(path, None)
            if isinstance(data, list):
                runtime_counts[name] = len(data)
            elif isinstance(data, dict):
                runtime_counts[name] = "OK_OBJECT"
            else:
                runtime_counts[name] = "MISSING_OR_BAD"
        else:
            runtime_counts[name] = "OK" if path.exists() else "MISSING"

    recommendations = []

    if feature_status["single_official_source"] == "NEEDS_REVIEW":
        recommendations.append("53: unify official final source between VVS final engine and full-slate threshold gate.")

    if feature_status["historical_real_odds_roi"] in ["MISSING", "PARTIAL"]:
        recommendations.append("54: build historical odds ROI audit. Use real entry/closing prices if available; otherwise mark as missing.")

    if feature_status["injuries_context"] in ["MISSING", "PARTIAL"]:
        recommendations.append("55: add or formalize injury impact layer before official buy.")

    if feature_status["advanced_pitcher_metrics"] in ["MISSING", "PARTIAL"]:
        recommendations.append("56: add advanced pitcher/team metrics audit and feature builder.")

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "bestDataset": best_dataset,
        "datasets": dataset_audit,
        "featureStatus": feature_status,
        "runtimeCounts": runtime_counts,
        "recommendations": recommendations,
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 52 BASEBALLPRED FEATURE PARITY AUDIT")
    lines.append("=" * 58)
    lines.append(f"Generated: {output['generatedAt']}")
    lines.append("")
    lines.append("Best dataset candidate:")
    if best_dataset:
        lines.append(f"- {best_dataset['name']} | Score={best_dataset['score']} | Rows={best_dataset['rows']} | Columns={best_dataset['columns']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Feature parity:")
    for k, v in feature_status.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Runtime counts:")
    for k, v in runtime_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Dataset audit:")
    for d in dataset_audit:
        lines.append(
            f"- {d['name']} | exists={d['exists']} rows={d['rows']} score={d['score']} "
            f"odds={d['has_odds']} injuries={d['has_injuries']} advancedPitcher={d['has_advanced_pitcher']}"
        )
    lines.append("")
    lines.append("Recommendations:")
    for r in recommendations:
        lines.append(f"- {r}")
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

