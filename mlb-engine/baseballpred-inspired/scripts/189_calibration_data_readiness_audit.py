from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "189_calibration_data_readiness_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-calibration-data-readiness-latest.json"

FILES = {
    "moneyline_feature_history": PROCESSED / "mlb_moneyline_features.csv",
    "moneyline_feature_full_context": PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    "moneyline_clean_record": ASTRO / "ASTRODDS-clean-moneyline-record.csv",
    "ou_clean_record": ASTRO / "ASTRODDS-clean-ou-record.csv",
    "market_lines": ASTRO / "ASTRODDS-historical-market-lines-template.csv",
    "odds_snapshot_ledger": ASTRO / "ASTRODDS-mlb-odds-snapshot-ledger.csv",
    "ou_v1_v2_ab_record": ASTRO / "ASTRODDS-ou-v1-v2-ab-test-record.csv",
    "moneyline_bbp_sidecar": ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json",
    "ou_bbp_sidecar": ASTRO / "ASTRODDS-bbp-sidecars-with-exact-bpen-whip35-latest.json",
}

def csv_info(path):
    if not path.exists():
        return {"exists": False, "rows": 0, "columns": []}
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            rows = list(reader)
        resolved = sum(1 for r in rows if str(r.get("result","")).lower() in ("win","loss","push"))
        pending = sum(1 for r in rows if str(r.get("result","")).lower() not in ("win","loss","push"))
        return {"exists": True, "rows": len(rows), "columns": cols[:80], "resolved": resolved, "pending": pending}
    except Exception as exc:
        return {"exists": True, "rows": 0, "columns": [], "error": str(exc)}

def json_info(path):
    if not path.exists():
        return {"exists": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = data.get("counts", {}) if isinstance(data, dict) else {}
        return {"exists": True, "keys": list(data.keys())[:30] if isinstance(data, dict) else [], "counts": counts}
    except Exception as exc:
        return {"exists": True, "error": str(exc)}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    info = {}
    for name, path in FILES.items():
        info[name] = json_info(path) if path.suffix.lower() == ".json" else csv_info(path)
        info[name]["path"] = str(path)

    ready = {
        "historical_moneyline_model_calibration": info["moneyline_feature_history"].get("rows",0) > 1000,
        "live_moneyline_result_calibration": info["moneyline_clean_record"].get("resolved",0) >= 30,
        "live_ou_result_calibration": info["ou_clean_record"].get("resolved",0) >= 30,
        "market_roi_clv_calibration": info["market_lines"].get("resolved",0) >= 30,
        "odds_clv_tracking": info["odds_snapshot_ledger"].get("rows",0) > 0,
    }

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "ready": ready,
        "files": info,
        "decision": "Use historical calibration where ready; keep live calibration paper-only until 30+ resolved picks per market.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 189 CALIBRATION DATA READINESS AUDIT",
        "=" * 70,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Readiness:",
    ]
    for k, v in ready.items():
        lines.append(f"- {k}: {'YES' if v else 'NO'}")
    lines += ["", "Files:"]
    for k, v in info.items():
        lines.append(f"- {k}: exists={v.get('exists')} rows={v.get('rows','')} resolved={v.get('resolved','')} pending={v.get('pending','')}")
    lines += ["", "Decision:", f"- {out['decision']}", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
