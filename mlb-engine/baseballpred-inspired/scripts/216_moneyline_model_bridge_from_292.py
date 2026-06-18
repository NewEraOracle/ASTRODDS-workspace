from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
CANDIDATE_CSV = ASTRO / "ASTRODDS-292-calibrated-candidate-board-latest.csv"

OUT_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-model-bridged-latest.json"
REPORT = REPORTS / "216_moneyline_model_bridge_from_292_report.txt"

STATUS_ORDER = {"OFFICIAL": 0, "A_PAPER": 1, "REVIEW": 2, "WATCH": 3, "BLOCKED": 4, "NO_BET": 5}

TEAM_ALIASES = {
    "athletics": "Athletics",
    "oakland athletics": "Athletics",
    "sacramento athletics": "Athletics",
    "st louis cardinals": "St. Louis Cardinals",
    "st. louis cardinals": "St. Louis Cardinals",
    "ny yankees": "New York Yankees",
    "new york yankees": "New York Yankees",
    "ny mets": "New York Mets",
    "new york mets": "New York Mets",
    "la dodgers": "Los Angeles Dodgers",
    "los angeles dodgers": "Los Angeles Dodgers",
    "la angels": "Los Angeles Angels",
    "los angeles angels": "Los Angeles Angels",
}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def canon(s):
    raw = str(s or "").strip()
    return TEAM_ALIASES.get(norm(raw), raw)

def parse_game(game):
    g = str(game or "").strip()
    for sep in [" @ ", " vs. ", " vs "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return canon(a), canon(h)
    return "", ""

def game_key(game="", away="", home=""):
    if game and (not away or not home):
        away, home = parse_game(game)
    if away and home:
        return f"{norm(canon(away))}@{norm(canon(home))}"
    return norm(game)

def team_key(team):
    return norm(canon(team))

def fnum(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%", "").replace("+", "").replace(",", ".")
    if not s:
        return default
    try:
        return float(s)
    except Exception:
        return default

def percent_to_prob(v):
    x = fnum(v, None)
    if x is None:
        return None
    if x > 1:
        return x / 100.0
    return x

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def status_from_candidate(candidate_level, edge_pct, reasons, mlb_status):
    c = str(candidate_level or "").upper()
    r = str(reasons or "").lower()
    s = str(mlb_status or "").lower()

    if "already_started_or_final" in r or "final" in s or "in progress" in s:
        return "BLOCKED"

    if c in ("OFFICIAL", "A_PICK", "A+", "A_PLUS", "ENGINE_BUY"):
        return "OFFICIAL"
    if c in ("A_PAPER", "ML_BBP_A_PLUS_PAPER"):
        return "A_PAPER"
    if c in ("REVIEW", "VALUE_LEAN", "ML_BBP_REVIEW"):
        return "REVIEW"
    if c in ("WATCH", "ACTION_LEAN", "ML_BBP_WATCH"):
        return "WATCH"

    if edge_pct is None:
        return "NO_BET"
    if edge_pct >= 10:
        return "REVIEW"
    if edge_pct >= 5:
        return "WATCH"
    return "NO_BET"

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    board_data = load_json(BOARD_JSON)
    rows = board_data.get("moneylineBoard", []) if isinstance(board_data, dict) else []
    candidates = read_csv(CANDIDATE_CSV)

    idx = {}
    for c in candidates:
        game = c.get("Game", "")
        pick = c.get("Pick", "")
        away, home = parse_game(game)
        key = (game_key(game, away, home), team_key(pick))
        if key[0] and key[1]:
            idx[key] = c

    applied = 0
    blocked_started = 0
    negative_edge = 0
    positive_edge = 0
    missing = 0

    for r in rows:
        away = r.get("awayTeam", "")
        home = r.get("homeTeam", "")
        game = r.get("game", "")
        pick = r.get("pick", "")
        key = (game_key(game, away, home), team_key(pick))
        c = idx.get(key)

        if not c:
            missing += 1
            continue

        model = percent_to_prob(c.get("ModelProbability"))
        edge_pct = fnum(c.get("Edge"), None)
        score = fnum(c.get("CandidateScore"), None)
        level = c.get("CandidateLevel", "")
        reasons = c.get("Reasons", "")
        mlb_status = c.get("MlbStatus", "")

        r["modelProbability"] = model if model is not None else ""
        r["edgePct"] = edge_pct if edge_pct is not None else ""
        r["candidateLevel"] = level
        r["candidateScore"] = score if score is not None else ""
        r["calibratedConfidence"] = c.get("CalibratedConfidence", "")
        r["rawConfidence"] = c.get("RawConfidence", "")
        r["mlbStatus"] = mlb_status
        r["lineups"] = c.get("Lineups", "")
        r["marketRowsFound"] = c.get("MarketRowsFound", "")
        r["candidateReasons"] = reasons

        new_status = status_from_candidate(level, edge_pct, reasons, mlb_status)
        r["status"] = new_status
        r["telegramEligible"] = False

        if score is not None:
            r["baseballPredScore"] = score

        if new_status == "BLOCKED":
            r["mainReason"] = "Moneyline model exists, but game is already started/final or not eligible."
            r["riskReason"] = reasons
            blocked_started += 1
        elif edge_pct is not None and edge_pct < 0:
            r["mainReason"] = "Model probability is below market price; no value edge."
            r["riskReason"] = f"Negative edge {edge_pct}% | {reasons}"
            negative_edge += 1
        elif new_status in ("REVIEW", "WATCH", "A_PAPER", "OFFICIAL"):
            r["mainReason"] = "Moneyline model/market bridge found a positive candidate."
            r["riskReason"] = reasons
            positive_edge += 1
        else:
            r["mainReason"] = "Moneyline model checked; no clean edge."
            r["riskReason"] = reasons

        if "ASTRODDS-292-calibrated-candidate-board-latest.csv" not in r.get("sourceFilesUsed", []):
            r.setdefault("sourceFilesUsed", []).append("ASTRODDS-292-calibrated-candidate-board-latest.csv")

        applied += 1

    rows.sort(key=lambda x: (STATUS_ORDER.get(x.get("status", "NO_BET"), 9), -fnum(x.get("baseballPredScore"), 0), -fnum(x.get("edgePct"), -999), -fnum(x.get("price"), 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    counts = {}
    for r in rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceBoard": str(BOARD_JSON),
        "sourceCandidates": str(CANDIDATE_CSV),
        "moneylineRows": len(rows),
        "candidateRows": len(candidates),
        "appliedRows": applied,
        "missingCandidateRows": missing,
        "blockedStartedOrFinal": blocked_started,
        "negativeEdgeRows": negative_edge,
        "positiveEdgeRows": positive_edge,
        "counts": counts,
        "moneylineBoard": rows,
        "rule": "MONEYLINE ONLY. Model bridge from 292 candidate board. Telegram unchanged.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Also replace the normal latest board so user's normal command shows bridged values.
    BOARD_JSON.write_text(json.dumps({
        "generatedAt": out["generatedAt"],
        "moneylineRows": len(rows),
        "counts": counts,
        "moneylineBoard": rows,
        "rule": out["rule"],
    }, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 216 MONEYLINE MODEL BRIDGE FROM 292",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Moneyline rows: {out['moneylineRows']}",
        f"Candidate rows: {out['candidateRows']}",
        f"Applied rows: {out['appliedRows']}",
        f"Missing candidate rows: {out['missingCandidateRows']}",
        f"Blocked started/final: {out['blockedStartedOrFinal']}",
        f"Negative edge rows: {out['negativeEdgeRows']}",
        f"Positive edge rows: {out['positiveEdgeRows']}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "MONEYLINE MODEL BRIDGED BOARD:"]
    for r in rows[:80]:
        lines.append(
            f"- #{r['rank']} | {r.get('status')} | {r.get('pick')} | {r.get('game')} | "
            f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('edgePct')} | "
            f"score={r.get('baseballPredScore')} | level={r.get('candidateLevel')} | mlbStatus={r.get('mlbStatus')} | {r.get('mainReason')}"
        )
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: MONEYLINE ONLY. Telegram unchanged."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
