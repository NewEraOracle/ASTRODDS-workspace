from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-two-side-model-coverage-latest.json"
REPORT = REPORTS / "234_moneyline_two_side_model_coverage_report.txt"

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def fnum(v, default=None):
    if v is None:
        return default
    try:
        s = str(v).strip().replace("%","").replace("+","").replace(",", ".")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def copy_game_status(dst, src):
    for k in ["mlbStatus","liveMlbStatus","cachedMlbStatus","candidateReasons","cachedCandidateReasons","liveStatusSource","liveGameDate","liveGamePk"]:
        if not dst.get(k) and src.get(k):
            dst[k] = src.get(k)

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    data = load(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r.get("game","")), []).append(r)

    total_games = len([g for g in by_game if g])
    two_row_games = 0
    one_model_games = 0
    filled = 0
    existing = 0
    previews = []

    for game, group in by_game.items():
        if len(group) < 2:
            continue
        two_row_games += 1
        model_rows = [r for r in group if fnum(r.get("modelProbability"), None) is not None]
        missing_rows = [r for r in group if fnum(r.get("modelProbability"), None) is None]
        existing += len(model_rows)

        if len(model_rows) == 1 and missing_rows:
            one_model_games += 1
            src = model_rows[0]
            src_model = fnum(src.get("modelProbability"), None)
            if src_model is None:
                continue
            for dst in missing_rows:
                opp_model = round(max(0.01, min(0.99, 1.0 - src_model)), 6)
                dst["modelProbability"] = opp_model
                dst["modelProbabilitySource"] = "two_side_inverse_from_opponent"
                dst["opponentModelPick"] = src.get("pick","")
                dst["opponentModelProbability"] = src_model
                dst["candidateLevel"] = "TWO_SIDE_FILL"
                copy_game_status(dst, src)
                dst["mainReason"] = "Model filled from opponent side using 1 - opponent modelProbability."
                dst["riskReason"] = f"Two-side fill from {src.get('pick','')} model={round(src_model*100,1)}%."
                previews.append((dst.get("pick",""), dst.get("game",""), opp_model, src.get("pick",""), src_model))
                filled += 1

        for r in model_rows:
            if not r.get("modelProbabilitySource"):
                r["modelProbabilitySource"] = "direct_model_candidate_or_existing"

    still_missing = 0
    for r in rows:
        model = fnum(r.get("modelProbability"), None)
        price = fnum(r.get("price"), None)
        if model is not None and price is not None:
            edge = round((model - price) * 100, 2)
            r["currentEdgePct"] = edge
            r["edgePct"] = edge
        else:
            still_missing += 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "totalGames": total_games,
        "gamesWithTwoRows": two_row_games,
        "gamesWithExactlyOneModel": one_model_games,
        "existingModelRows": existing,
        "filledRows": filled,
        "stillMissingRows": still_missing,
        "moneylineBoard": rows,
        "rule": "Opponent modelProbability filled as 1 - known side modelProbability.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(rows), "moneylineBoard": rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 234 MONEYLINE TWO-SIDE MODEL COVERAGE",
        "="*76,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows: {len(rows)}",
        f"Total games: {total_games}",
        f"Games with two rows: {two_row_games}",
        f"Games with one model side: {one_model_games}",
        f"Existing model rows: {existing}",
        f"Filled model rows: {filled}",
        f"Still missing rows: {still_missing}",
        "",
        "Filled preview:",
    ]
    if previews:
        for p,g,m,op,om in previews[:60]:
            lines.append(f"- {p} | {g} | model={round(m*100,2)}% | from {op}={round(om*100,2)}%")
    else:
        lines.append("- none")

    lines += ["", "Top board by edge:"]
    for r in sorted(rows, key=lambda x: fnum(x.get("currentEdgePct"), -999), reverse=True)[:80]:
        lines.append(f"- {r.get('pick')} | {r.get('game')} | price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct','')} | source={r.get('modelProbabilitySource','')}")
    lines += ["", f"JSON: {OUT_JSON}", "Rule: model coverage only. No betting automation."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
