from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "172_full_baseballpred_gap_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-full-baseballpred-gap-report-latest.json"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    readiness = load(ASTRO / "ASTRODDS-baseballpred-moneyline-readiness-latest.json")
    roi = load(ASTRO / "ASTRODDS-roi-clv-backtest-latest.json")
    ml = load(ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json")
    ou = load(ASTRO / "ASTRODDS-ou-v2-batting-context-score-latest.json")

    read = readiness.get("readiness", {}) if isinstance(readiness, dict) else {}
    gaps = []
    for item in ["OBP_162","SLG_162","Strt_WHIP_35","Strt_SO_perc_10","Bpen_WHIP_75","Bpen_WHIP_35","Bpen_SO_perc_75","historical_moneyline_odds","historical_ou_lines"]:
        if not read.get(item):
            gaps.append(item)

    if roi.get("status") != "READY":
        gaps.append("real ROI/CLV market backtest rows")

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "moneylineSidecarCandidates": ml.get("counts", {}),
        "ouSidecarCandidates": ou.get("counts", {}),
        "remainingGaps": gaps,
        "liveRecommendation": "Keep live 135/136 unchanged until A/B + ROI/CLV proves better.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 172 FULL BASEBALLPRED GAP REPORT",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Moneyline sidecar:",
        f"- {out['moneylineSidecarCandidates']}",
        "",
        "O/U sidecar:",
        f"- {out['ouSidecarCandidates']}",
        "",
        "Remaining gaps:",
    ]
    lines += [f"- {g}" for g in gaps] if gaps else ["- none"]
    lines += ["", "Recommendation:", f"- {out['liveRecommendation']}", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
