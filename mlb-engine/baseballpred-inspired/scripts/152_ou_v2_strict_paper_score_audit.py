from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

INPUT_JSON = ASTRO / "ASTRODDS-ou-live-context-enrichment-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-ou-v2-strict-paper-score-latest.json"
REPORT = REPORTS / "152_ou_v2_strict_paper_score_audit_report.txt"

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def score_candidate(c):
    base_score = fnum(c.get("qualityScore", 0))
    edge = fnum(c.get("edgeRuns", 0))
    grade = c.get("gradeV2", "")
    context_ready = bool(c.get("contextReady"))
    flags = c.get("contextFlags", []) or []

    score = base_score

    # Keep EdgeRuns as the strongest factor.
    if edge >= 2.25:
        score += 10
    elif edge >= 1.75:
        score += 5
    elif edge < 1.40:
        score -= 20

    # Context confirmation helps, but does not create a pick by itself.
    if context_ready:
        score += 5

    # Bullpen fatigue can support Over, but it is noisy; small bonus only.
    if any("bullpen fatigue" in str(x).lower() for x in flags):
        score += 3

    # Lineup/injury context means context exists, not automatically good or bad.
    if any("lineup" in str(x).lower() for x in flags):
        score += 1

    # Weather/park context exists; small bonus only.
    if any("weather" in str(x).lower() or "park" in str(x).lower() for x in flags):
        score += 1

    score = max(0, min(100, round(score, 2)))

    if grade == "A+" and edge >= 1.75 and score >= 90:
        strict_grade = "V2_A_PLUS_PAPER"
        action = "PAPER_TRACK"
    elif grade in ("A+", "A_REVIEW") and edge >= 1.40 and score >= 80:
        strict_grade = "V2_REVIEW"
        action = "REVIEW_ONLY"
    else:
        strict_grade = "V2_WATCH"
        action = "NO_ACTION"

    return score, strict_grade, action

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = load_json(INPUT_JSON, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []

    scored = []
    for c in candidates:
        score, strict_grade, action = score_candidate(c)
        x = dict(c)
        x["strictV2Score"] = score
        x["strictV2Grade"] = strict_grade
        x["strictV2Action"] = action
        x["strictV2Rule"] = "Paper only. Requires V2 A+, EdgeRuns >= 1.75, context-ready, and score >= 90 for V2_A_PLUS_PAPER."
        scored.append(x)

    scored.sort(key=lambda x: (
        0 if x["strictV2Grade"] == "V2_A_PLUS_PAPER" else 1 if x["strictV2Grade"] == "V2_REVIEW" else 2,
        -fnum(x.get("strictV2Score", 0)),
        -fnum(x.get("edgeRuns", 0)),
    ))

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_paper_only",
        "rules": {
            "V2_A_PLUS_PAPER": "gradeV2 A+, EdgeRuns >= 1.75, strict score >= 90",
            "V2_REVIEW": "A+/A_REVIEW, EdgeRuns >= 1.40, strict score >= 80",
            "liveTelegram": "unchanged; 136 remains the live O/U A+ sender",
        },
        "counts": {
            "inputCandidates": len(candidates),
            "paperAPlus": sum(1 for x in scored if x["strictV2Grade"] == "V2_A_PLUS_PAPER"),
            "review": sum(1 for x in scored if x["strictV2Grade"] == "V2_REVIEW"),
            "watch": sum(1 for x in scored if x["strictV2Grade"] == "V2_WATCH"),
        },
        "candidates": scored,
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 152 O/U V2 STRICT PAPER SCORE AUDIT",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Paper only.",
        "- Does not touch live Telegram.",
        "- 136 remains current live O/U A+ sender.",
        "",
        f"Input: {INPUT_JSON}",
        f"Output: {OUT_JSON}",
        "",
        "Counts:",
        f"- inputCandidates: {out['counts']['inputCandidates']}",
        f"- V2_A_PLUS_PAPER: {out['counts']['paperAPlus']}",
        f"- V2_REVIEW: {out['counts']['review']}",
        f"- V2_WATCH: {out['counts']['watch']}",
        "",
        "Top scored candidates:",
    ]

    for x in scored[:12]:
        lines.append(
            f"- {x['strictV2Grade']} | {x['strictV2Action']} | {x.get('game')} | {x.get('pick')} | "
            f"EdgeRuns=+{fnum(x.get('edgeRuns')):.2f} | BaseGrade={x.get('gradeV2')} | "
            f"BaseScore={x.get('qualityScore')} | StrictScore={x.get('strictV2Score')} | "
            f"ContextReady={x.get('contextReady')}"
        )

    lines += [
        "",
        "Decision:",
        "- Use V2_A_PLUS_PAPER for paper A/B test only.",
        "- Do not replace live O/U until V2 paper results beat current 136 live rule.",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
