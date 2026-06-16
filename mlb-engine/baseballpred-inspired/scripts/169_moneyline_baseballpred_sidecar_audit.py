from pathlib import Path
from datetime import datetime
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"
BRIDGE_JSON = ASTRO / "ASTRODDS-baseballpred-feature-bridge-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json"
REPORT = REPORTS / "169_moneyline_baseballpred_sidecar_audit_report.txt"

def norm(s):
    s = str(s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def fnum(v, default=0.0):
    try: return float(v)
    except Exception: return default

def find_bridge(game, bridge):
    ng = norm(game)
    for k, v in bridge.items():
        if ng and ng in k:
            return v
    # fuzzy
    game_words = set(ng.split())
    best = None
    best_score = 0
    for k, v in bridge.items():
        score = len(game_words.intersection(set(k.split())))
        if score > best_score:
            best, best_score = v, score
    return best if best_score >= 3 else None

def score_pick(row, features):
    base = fnum(row.get("model", row.get("modelProbability", row.get("model_pct", 0))) or 0)
    edge = fnum(row.get("edge", row.get("edgePct", 0)) or 0)
    if base <= 1: base *= 100
    if edge <= 1: edge *= 100

    score = min(100, max(0, base + edge / 2))
    reasons = []

    if features:
        groups = features.get("features", {})
        if "starter_WHIP_or_proxy" in groups or "starter_SO_or_proxy" in groups:
            score += 3; reasons.append("pitcher context available")
        if "bullpen_WHIP_or_proxy" in groups or "bullpen_fatigue" in groups:
            score += 3; reasons.append("bullpen context available")
        if "lineup_strength" in groups or "OBP_162_or_proxy" in groups or "SLG_162_or_proxy" in groups:
            score += 3; reasons.append("lineup/batting context available")
        if "weather_or_park" in groups:
            score += 1; reasons.append("weather/park context available")
    else:
        score -= 5; reasons.append("no bridge context matched")

    score = round(max(0, min(100, score)), 2)
    grade = "ML_BBP_A_PLUS_PAPER" if score >= 82 and edge >= 12 else "ML_BBP_REVIEW" if score >= 72 else "ML_BBP_WATCH"
    return score, grade, reasons

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    board = load(BOARD_JSON, {})
    bridge_data = load(BRIDGE_JSON, {})
    bridge = bridge_data.get("bridge", {}) if isinstance(bridge_data, dict) else {}

    candidates = []
    for key in ["aPicks", "moneylineAPicks", "candidates", "rows"]:
        vals = board.get(key, []) if isinstance(board, dict) else []
        if isinstance(vals, list):
            candidates.extend(vals)

    seen = set()
    out_rows = []
    for r in candidates:
        game = r.get("game", "")
        pick = r.get("pick", "")
        if not game or not pick:
            continue
        k = game + "|" + pick
        if k in seen:
            continue
        seen.add(k)
        ctx = find_bridge(game, bridge)
        score, grade, reasons = score_pick(r, ctx)
        out_rows.append({
            **r,
            "baseballPredContextMatched": bool(ctx),
            "baseballPredFeatureGroups": list((ctx or {}).get("features", {}).keys()) if ctx else [],
            "moneylineBaseballPredScore": score,
            "moneylineBaseballPredGrade": grade,
            "moneylineBaseballPredReasons": reasons,
            "source": "sidecar_only",
        })

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "moneyline_baseballpred_sidecar_only",
        "rules": {
            "liveTelegram": "unchanged; 135 remains live",
            "paperUse": "Compare with current Moneyline A/A+ before replacing live."
        },
        "counts": {
            "candidates": len(out_rows),
            "aPlusPaper": sum(1 for r in out_rows if r["moneylineBaseballPredGrade"] == "ML_BBP_A_PLUS_PAPER"),
            "review": sum(1 for r in out_rows if r["moneylineBaseballPredGrade"] == "ML_BBP_REVIEW"),
            "watch": sum(1 for r in out_rows if r["moneylineBaseballPredGrade"] == "ML_BBP_WATCH"),
        },
        "candidates": out_rows,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 169 MONEYLINE BASEBALLPRED SIDECAR AUDIT",
        "=" * 74,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Counts:",
        f"- candidates: {out['counts']['candidates']}",
        f"- ML_BBP_A_PLUS_PAPER: {out['counts']['aPlusPaper']}",
        f"- ML_BBP_REVIEW: {out['counts']['review']}",
        f"- ML_BBP_WATCH: {out['counts']['watch']}",
        "",
        "Top candidates:",
    ]
    for r in out_rows[:15]:
        lines.append(f"- {r['moneylineBaseballPredGrade']} | {r.get('pick')} | {r.get('game')} | Score={r['moneylineBaseballPredScore']} | Context={r['baseballPredContextMatched']} | Reasons={','.join(r['moneylineBaseballPredReasons'])}")
    lines += ["", "Decision:", "- Keep 135 live unchanged until sidecar proves better.", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
