from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

INPUT_JSON = ASTRO / "ASTRODDS-ou-v2-batting-context-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-ou-v2-batting-context-score-latest.json"
REPORT = REPORTS / "160_ou_v2_batting_context_score_audit_report.txt"

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

def score(c):
    base = fnum(c.get("strictV2Score"), 0)
    signal = c.get("battingContextSignal", "")
    adj, reasons = 0, []

    if signal == "OVER_SUPPORT":
        adj += 5
        reasons.append("lineup batting supports Over")
    elif signal == "OVER_CAUTION":
        adj -= 8
        reasons.append("lineup batting caution")
    elif signal == "NO_MATCH":
        adj -= 3
        reasons.append("no batting match")

    missing = fnum(c.get("home_missing_key_batters_count"), 0) + fnum(c.get("away_missing_key_batters_count"), 0)
    if missing >= 2:
        adj -= 5
        reasons.append("missing key batters")

    final = max(0, min(100, round(base + adj, 2)))
    grade = "V2_BATTING_A_PLUS_PAPER" if c.get("strictV2Grade") == "V2_A_PLUS_PAPER" and final >= 90 else (
        "V2_BATTING_REVIEW" if final >= 80 else "V2_BATTING_WATCH"
    )
    return final, grade, reasons

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = load_json(INPUT_JSON, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    scored = []

    for c in candidates:
        x = dict(c)
        final, grade, reasons = score(x)
        x["battingAdjustedV2Score"] = final
        x["battingAdjustedV2Grade"] = grade
        x["battingAdjustedReasons"] = reasons
        scored.append(x)

    scored.sort(key=lambda x: (
        0 if x.get("battingAdjustedV2Grade") == "V2_BATTING_A_PLUS_PAPER" else 1 if x.get("battingAdjustedV2Grade") == "V2_BATTING_REVIEW" else 2,
        -fnum(x.get("battingAdjustedV2Score")),
        -fnum(x.get("edgeRuns")),
    ))

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_batting_score_only",
        "rules": {"liveTelegram": "unchanged", "A_PLUS": "strict V2 A+ and batting adjusted score >= 90", "REVIEW": "batting adjusted score >= 80"},
        "counts": {
            "inputCandidates": len(candidates),
            "battingAPlus": sum(1 for x in scored if x.get("battingAdjustedV2Grade") == "V2_BATTING_A_PLUS_PAPER"),
            "battingReview": sum(1 for x in scored if x.get("battingAdjustedV2Grade") == "V2_BATTING_REVIEW"),
            "battingWatch": sum(1 for x in scored if x.get("battingAdjustedV2Grade") == "V2_BATTING_WATCH"),
        },
        "candidates": scored,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 160 O/U V2 BATTING CONTEXT SCORE AUDIT",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Adjusts V2 strict score using lineup OBP/SLG proxy context.",
        "",
        "Counts:",
        f"- inputCandidates: {out['counts']['inputCandidates']}",
        f"- V2_BATTING_A_PLUS_PAPER: {out['counts']['battingAPlus']}",
        f"- V2_BATTING_REVIEW: {out['counts']['battingReview']}",
        f"- V2_BATTING_WATCH: {out['counts']['battingWatch']}",
        "",
        "Top candidates:",
    ]
    for x in scored[:12]:
        lines.append(
            f"- {x.get('battingAdjustedV2Grade')} | {x.get('game')} | {x.get('pick')} | "
            f"EdgeRuns=+{fnum(x.get('edgeRuns')):.2f} | StrictScore={x.get('strictV2Score')} | "
            f"BattingScore={x.get('battingAdjustedV2Score')} | Signal={x.get('battingContextSignal')} | "
            f"Reasons={','.join(x.get('battingAdjustedReasons', [])) if x.get('battingAdjustedReasons') else 'none'}"
        )

    lines += ["", "Decision:", "- Use for paper comparison only.", "- If batting-adjusted V2 wins, later we can upgrade 136."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
