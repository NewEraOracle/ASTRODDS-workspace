from pathlib import Path
from datetime import datetime
import csv, json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "167_baseballpred_moneyline_readiness_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-baseballpred-moneyline-readiness-latest.json"

CANDIDATE_FILES = [
    PROCESSED / "mlb_moneyline_features.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers.csv",
    PROCESSED / "mlb_moneyline_features_with_bullpen.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    PROCESSED / "mlb_lineup_player_features.csv",
    PROCESSED / "mlb_bullpen_features.csv",
    ASTRO / "ASTRODDS-advanced-pitcher-team-metrics-latest.csv",
    ASTRO / "VVS-pitcher-context-latest.csv",
    ASTRO / "VVS-bullpen-context-latest.csv",
]

TRUE_FEATURE_TERMS = {
    "OBP_162": ["obp_162", "obp"],
    "SLG_162": ["slg_162", "slg"],
    "Strt_WHIP_35": ["strt_whip_35", "starter_whip_35", "pitcher_whip", "whip"],
    "Strt_SO_perc_10": ["strt_so_perc_10", "starter_so", "pitcher_so", "strikeout"],
    "Bpen_WHIP_75": ["bpen_whip_75", "bullpen_whip_75", "bullpen_whip", "whip"],
    "Bpen_WHIP_35": ["bpen_whip_35", "bullpen_whip_35"],
    "Bpen_SO_perc_75": ["bpen_so_perc_75", "bullpen_so", "reliever_so", "strikeout"],
    "historical_moneyline_odds": ["moneyline", "odds", "price", "close", "open"],
    "historical_ou_lines": ["total", "over", "under", "line", "close", "open"],
}

def sniff(path):
    if not path.exists():
        return [], 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            n = sum(1 for _ in reader)
            return cols, n
    except Exception:
        return [], 0

def has_terms(cols, terms):
    low = [c.lower() for c in cols]
    return [c for c in cols if any(t in c.lower() for t in terms)]

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    files = []
    aggregate = {k: [] for k in TRUE_FEATURE_TERMS}

    for p in CANDIDATE_FILES:
        cols, rows = sniff(p)
        if not cols:
            continue
        item = {"path": str(p), "rows": rows, "columns": cols[:120], "matches": {}}
        for feat, terms in TRUE_FEATURE_TERMS.items():
            matches = has_terms(cols, terms)
            item["matches"][feat] = matches[:30]
            if matches:
                aggregate[feat].append({"path": str(p), "columns": matches[:30], "rows": rows})
        files.append(item)

    readiness = {feat: bool(vals) for feat, vals in aggregate.items()}

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "readiness_audit_only",
        "readiness": readiness,
        "aggregateMatches": aggregate,
        "files": files,
        "decision": "Build BaseballPred moneyline sidecar from available true/proxy features. Do not replace live until backtested.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 167 BASEBALLPRED MONEYLINE READINESS AUDIT",
        "=" * 76,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Readiness:",
    ]
    for k, v in readiness.items():
        lines.append(f"- {k}: {'YES' if v else 'NO'}")
    lines += ["", "Best source matches:"]
    for k, vals in aggregate.items():
        lines.append(f"- {k}: {len(vals)} source(s)")
        for v in vals[:3]:
            lines.append(f"  - {v['path']} | rows={v['rows']} | cols={v['columns'][:8]}")
    lines += ["", "Decision:", "- Moneyline BaseballPred sidecar can be built from available processed files.", "- True historical market ROI/CLV still depends on having real odds/closing lines.", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
