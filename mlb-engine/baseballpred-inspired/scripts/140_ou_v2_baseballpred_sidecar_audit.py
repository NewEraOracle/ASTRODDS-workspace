from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OU_JSON = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-ou-v2-baseballpred-sidecar-latest.json"
REPORT = REPORTS / "140_ou_v2_baseballpred_sidecar_audit_report.txt"

ET = ZoneInfo("America/New_York")

# V2 is sidecar/audit only.
# It does not send Telegram and does not replace 136 yet.

def now_et():
    return datetime.now(ET).isoformat()

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def get(row, keys, default=""):
    for k in keys:
        if isinstance(row, dict) and k in row and row[k] not in (None, ""):
            return row[k]
    return default

def parse_sample_games(reason):
    m = re.search(r"sample_games=([0-9]+)", str(reason or ""))
    if not m:
        return 0
    return int(m.group(1))

def american_price_ok(price):
    # Avoid paying too much juice for O/U paper signals.
    p = to_float(price, 0)
    return -125 <= p <= 115

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

def edge_to_probability(edge_runs):
    # Conservative probability proxy until true distribution model is trained.
    # +1.75 runs roughly maps near 61%, +2.50 near 68%.
    return max(0.50, min(0.75, sigmoid((edge_runs - 0.55) / 1.15)))

def quality_score(edge_runs, sample_games, price_ok, category):
    score = 0
    if category == "O/U_PICK":
        score += 20
    if edge_runs >= 2.25:
        score += 45
    elif edge_runs >= 1.75:
        score += 35
    elif edge_runs >= 1.40:
        score += 25
    else:
        score += 10

    if sample_games >= 10:
        score += 20
    elif sample_games >= 6:
        score += 12

    if price_ok:
        score += 15
    else:
        score -= 20

    return max(0, min(100, score))

def v2_grade(edge_runs, sample_games, price_ok, category):
    # Telegram-safe candidates.
    if category == "O/U_PICK" and edge_runs >= 1.75 and sample_games >= 10 and price_ok:
        return "A+"
    # Strong audit only.
    if category == "O/U_PICK" and edge_runs >= 1.40 and sample_games >= 10 and price_ok:
        return "A_REVIEW"
    return "WATCH"

def explain(row, edge_runs, sample_games, price_ok, prob_proxy, grade):
    return (
        f"Projected total is {edge_runs:.2f} runs above market line. "
        f"Probability proxy around {prob_proxy*100:.1f}%. "
        f"Sample games={sample_games}. "
        f"Price OK={price_ok}. "
        f"V2 grade={grade}."
    )

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = load_json(OU_JSON, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []

    enhanced = []
    for r in candidates:
        if not isinstance(r, dict):
            continue

        category = str(r.get("category", "")).strip().upper()
        game = str(r.get("game", "")).strip()
        pick = str(r.get("pick", "")).strip()
        line = to_float(get(r, ["line"], 0))
        projected = to_float(get(r, ["projectedTotalRuns", "projected", "projectedTotal"], 0))
        edge_runs = to_float(get(r, ["edgeRuns", "edge_runs"], projected - line))
        price = get(r, ["priceAmerican", "price", "odds"], "")
        reason = r.get("reason", "")
        sample_games = parse_sample_games(reason)
        price_ok = american_price_ok(price)
        prob_proxy = edge_to_probability(edge_runs)
        grade = v2_grade(edge_runs, sample_games, price_ok, category)
        score = quality_score(edge_runs, sample_games, price_ok, category)

        enhanced.append({
            "date": r.get("date", ""),
            "game": game,
            "awayTeam": r.get("awayTeam", ""),
            "homeTeam": r.get("homeTeam", ""),
            "pick": pick,
            "line": line,
            "projectedTotalRuns": projected,
            "edgeRuns": edge_runs,
            "priceAmerican": price,
            "categoryV1": category,
            "gradeV2": grade,
            "qualityScore": score,
            "probabilityProxyOver": round(prob_proxy, 4) if pick.lower().startswith("over") else "",
            "sampleGames": sample_games,
            "priceOk": price_ok,
            "stakeV2": "3% max / paper" if grade == "A+" else "No Telegram / review only",
            "v2Explanation": explain(r, edge_runs, sample_games, price_ok, prob_proxy, grade),
            "reasonV1": reason,
        })

    enhanced.sort(key=lambda x: (
        0 if x["gradeV2"] == "A+" else 1 if x["gradeV2"] == "A_REVIEW" else 2,
        -float(x["edgeRuns"]),
        -float(x["qualityScore"]),
    ))

    out = {
        "generatedAt": now_et(),
        "mode": "sidecar_audit_only",
        "model": "ASTRODDS_OU_V2_BASEBALLPRED_SIDECAR",
        "rules": {
            "A_PLUS": "O/U_PICK, EdgeRuns >= 1.75, sampleGames >= 10, price between -125 and +115",
            "A_REVIEW": "O/U_PICK, EdgeRuns >= 1.40, sampleGames >= 10, price between -125 and +115",
            "WATCH": "everything else",
            "telegram": "not sent by this sidecar",
        },
        "counts": {
            "inputCandidates": len(candidates),
            "aPlus": sum(1 for x in enhanced if x["gradeV2"] == "A+"),
            "aReview": sum(1 for x in enhanced if x["gradeV2"] == "A_REVIEW"),
            "watch": sum(1 for x in enhanced if x["gradeV2"] == "WATCH"),
        },
        "candidates": enhanced,
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 140 O/U V2 BASEBALLPRED SIDECAR AUDIT",
        "=" * 70,
        f"Generated ET: {now_et()}",
        "",
        "Rules:",
        "- Sidecar audit only.",
        "- Does not send Telegram.",
        "- Does not replace 136 yet.",
        "- Uses O/U V1 projected totals plus BaseballPred-style quality filters.",
        "- A+ requires EdgeRuns >= 1.75, sampleGames >= 10, price OK.",
        "",
        f"Input JSON: {OU_JSON}",
        f"Output JSON: {OUT_JSON}",
        "",
        "Counts:",
        f"- inputCandidates: {out['counts']['inputCandidates']}",
        f"- A+: {out['counts']['aPlus']}",
        f"- A_REVIEW: {out['counts']['aReview']}",
        f"- WATCH: {out['counts']['watch']}",
        "",
        "Top V2 candidates:",
    ]

    for x in enhanced[:12]:
        lines.append(
            f"- {x['gradeV2']} | {x['game']} | {x['pick']} | "
            f"Line={x['line']} | Projected={x['projectedTotalRuns']} | "
            f"EdgeRuns=+{x['edgeRuns']:.2f} | ProbProxy={x['probabilityProxyOver']} | "
            f"Price={x['priceAmerican']} | Score={x['qualityScore']} | "
            f"Sample={x['sampleGames']}"
        )

    lines.extend([
        "",
        "Rule: Paper/manual sidecar only. No real-money automation.",
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
