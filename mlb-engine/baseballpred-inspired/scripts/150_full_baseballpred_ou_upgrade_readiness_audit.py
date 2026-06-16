from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

READINESS = ASTRO / "ASTRODDS-baseballpred-data-readiness-latest.json"
FEATURES = ASTRO / "ASTRODDS-ou-full-baseballpred-features-latest.json"
PROB_MODEL = ASTRO / "ASTRODDS-ou-full-probability-sidecar-model-v1.json"
V1V2 = ASTRO / "ASTRODDS-ou-v1-v2-comparison-latest.json"

OUT_JSON = ASTRO / "ASTRODDS-full-baseballpred-ou-upgrade-readiness-latest.json"
REPORT = REPORTS / "150_full_baseballpred_ou_upgrade_readiness_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    readiness = load(READINESS)
    features = load(FEATURES)
    model = load(PROB_MODEL)
    compare = load(V1V2)

    complete = readiness.get("complete", {}) if isinstance(readiness, dict) else {}
    metrics = model.get("metrics", {}) if isinstance(model, dict) else {}
    test_metrics = metrics.get("test2024Plus", {}) if isinstance(metrics, dict) else {}

    blockers = []
    if not complete.get("advanced_batting"):
        blockers.append("Missing true OBP_162 / SLG_162 batting source.")
    if not complete.get("starter_pitching"):
        blockers.append("Missing true starter WHIP / SO% source.")
    if not complete.get("bullpen"):
        blockers.append("Missing true bullpen WHIP / SO% source.")
    if not complete.get("historical_totals_lines"):
        blockers.append("Missing true historical sportsbook O/U lines.")
    if not complete.get("weather_ballpark"):
        blockers.append("Missing robust weather/park source for historical and live adjustment.")

    decision = "DO_NOT_MERGE_TO_LIVE"
    if not blockers and test_metrics:
        ll = test_metrics.get("logLoss")
        base = test_metrics.get("baselineLogLoss")
        if isinstance(ll, (int,float)) and isinstance(base, (int,float)) and ll < base:
            decision = "READY_FOR_PAPER_A_B_TEST"

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "full_upgrade_readiness_only",
        "decision": decision,
        "blockers": blockers,
        "testMetrics": test_metrics,
        "currentLiveRecommendation": "Keep 136 O/U A+ live rule: EdgeRuns >= +1.75. Keep full upgrade sidecar until blockers are resolved.",
        "rollback": {
            "gitTag": "safe-before-full-baseballpred-upgrade",
            "command": "git checkout safe-before-full-baseballpred-upgrade"
        },
        "inputs": {
            "readiness": str(READINESS),
            "features": str(FEATURES),
            "probModel": str(PROB_MODEL),
            "v1v2Compare": str(V1V2),
        }
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 150 FULL BASEBALLPRED O/U UPGRADE READINESS AUDIT",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar/readiness only.",
        "- Does not touch live Telegram.",
        "- Decides whether full BaseballPred O/U is ready to replace live.",
        "",
        f"Decision: {decision}",
        "",
        "Blockers:",
    ]
    if blockers:
        for b in blockers:
            lines.append(f"- {b}")
    else:
        lines.append("- none")

    lines += [
        "",
        "Test metrics:",
        f"- {test_metrics}",
        "",
        "Current live recommendation:",
        f"- {out['currentLiveRecommendation']}",
        "",
        "Rollback:",
        f"- git checkout {out['rollback']['gitTag']}",
        "",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
