from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "177_true_feature_final_gap_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-true-feature-final-gap-latest.json"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    bpen = load(ASTRO / "ASTRODDS-exact-bpen-whip35-latest.json")
    market = load(ASTRO / "ASTRODDS-market-data-gap-latest.json")
    ml = load(ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json")
    ou = load(ASTRO / "ASTRODDS-ou-v2-batting-context-score-latest.json")

    gaps = []
    if bpen.get("decision") != "EXACT_BPen_WHIP35_READY":
        gaps.append("Bpen_WHIP_35 exact source still missing")
    for g in market.get("remainingGaps", []):
        gaps.append(g)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "moneylineSidecar": ml.get("counts", {}),
        "ouSidecar": ou.get("counts", {}),
        "bpenWhip35Status": bpen.get("decision", "UNKNOWN"),
        "marketDataStatus": market.get("status", "UNKNOWN"),
        "remainingGaps": gaps,
        "liveRecommendation": "Keep 135/136 live until market data + A/B test proves better.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 177 TRUE FEATURE FINAL GAP REPORT",
        "=" * 66,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Sidecars:",
        f"- Moneyline: {out['moneylineSidecar']}",
        f"- O/U: {out['ouSidecar']}",
        "",
        f"Bpen WHIP35: {out['bpenWhip35Status']}",
        f"Market data: {out['marketDataStatus']}",
        "",
        "Remaining gaps:",
    ]
    lines += [f"- {g}" for g in gaps] if gaps else ["- none"]
    lines += ["", "Recommendation:", f"- {out['liveRecommendation']}", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
