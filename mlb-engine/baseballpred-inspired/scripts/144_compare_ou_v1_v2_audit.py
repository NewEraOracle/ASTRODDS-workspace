from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OU_V1 = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
OU_V2 = ASTRO / "ASTRODDS-ou-v2-baseballpred-sidecar-latest.json"
REPORT = REPORTS / "144_compare_ou_v1_v2_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-ou-v1-v2-comparison-latest.json"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def key(r):
    return f"{r.get('game','')}|{r.get('pick','')}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    v1 = load(OU_V1)
    v2 = load(OU_V2)

    v1_candidates = v1.get("candidates", []) if isinstance(v1, dict) else []
    v2_candidates = v2.get("candidates", []) if isinstance(v2, dict) else []

    v2_by_key = {key(r): r for r in v2_candidates}
    rows = []

    for r in v1_candidates:
        k = key(r)
        v2r = v2_by_key.get(k, {})
        rows.append({
            "game": r.get("game", ""),
            "pick": r.get("pick", ""),
            "v1Category": r.get("category", ""),
            "edgeRuns": r.get("edgeRuns", ""),
            "projectedTotalRuns": r.get("projectedTotalRuns", ""),
            "priceAmerican": r.get("priceAmerican", ""),
            "v2Grade": v2r.get("gradeV2", "MISSING"),
            "v2Score": v2r.get("qualityScore", ""),
            "v2ProbProxy": v2r.get("probabilityProxyOver", ""),
        })

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_compare_only",
        "counts": {
            "v1Candidates": len(v1_candidates),
            "v2Candidates": len(v2_candidates),
            "v2APlus": sum(1 for r in v2_candidates if r.get("gradeV2") == "A+"),
            "v2AReview": sum(1 for r in v2_candidates if r.get("gradeV2") == "A_REVIEW"),
        },
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 144 COMPARE O/U V1 VS V2 AUDIT",
        "=" * 64,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar comparison only.",
        "- Does not send Telegram.",
        "",
        f"V1 candidates: {len(v1_candidates)}",
        f"V2 candidates: {len(v2_candidates)}",
        f"V2 A+: {out['counts']['v2APlus']}",
        f"V2 A_REVIEW: {out['counts']['v2AReview']}",
        "",
        "Comparison rows:",
    ]

    for r in rows[:15]:
        lines.append(
            f"- {r['v2Grade']} | {r['v1Category']} | {r['game']} | {r['pick']} | "
            f"EdgeRuns={r['edgeRuns']} | V2Score={r['v2Score']} | ProbProxy={r['v2ProbProxy']}"
        )

    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
