from pathlib import Path
from datetime import datetime
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BPEN_CSV = ASTRO / "ASTRODDS-bpen-whip35-exact-statsapi-latest.csv"
ML_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json"
OU_JSON = ASTRO / "ASTRODDS-ou-v2-batting-context-score-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-bbp-sidecars-with-exact-bpen-whip35-latest.json"
REPORT = REPORTS / "184_merge_exact_bpen_whip35_into_bbp_sidecars_report.txt"

def norm(s):
    s = str(s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def find_team_whip(team_name, bpen_rows):
    nt = norm(team_name)
    for r in bpen_rows:
        if norm(r.get("teamName")) == nt:
            return r
    # fuzzy contains
    for r in bpen_rows:
        rt = norm(r.get("teamName"))
        if nt and (nt in rt or rt in nt):
            return r
    return None

def parse_game_teams(game):
    g = str(game or "")
    for sep in [" @ ", " vs. ", " vs "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return a.strip(), h.strip()
    return "", ""

def add_bpen_to_candidate(c, bpen_rows):
    x = dict(c)
    game = x.get("game", "")
    away, home = parse_game_teams(game)

    away_bpen = find_team_whip(away, bpen_rows) if away else None
    home_bpen = find_team_whip(home, bpen_rows) if home else None

    x["exactBpenWhip35Available"] = bool(away_bpen or home_bpen)
    if away_bpen:
        x["away_Bpen_WHIP_35_exact"] = away_bpen.get("Bpen_WHIP_35", "")
        x["away_bpen_games_35"] = away_bpen.get("games_in_window", "")
    if home_bpen:
        x["home_Bpen_WHIP_35_exact"] = home_bpen.get("Bpen_WHIP_35", "")
        x["home_bpen_games_35"] = home_bpen.get("games_in_window", "")
    return x

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    bpen_rows = read_csv(BPEN_CSV)
    ml = load_json(ML_JSON, {})
    ou = load_json(OU_JSON, {})

    ml_candidates = ml.get("candidates", []) if isinstance(ml, dict) else []
    ou_candidates = ou.get("candidates", []) if isinstance(ou, dict) else []

    ml_out = [add_bpen_to_candidate(c, bpen_rows) for c in ml_candidates]
    ou_out = [add_bpen_to_candidate(c, bpen_rows) for c in ou_candidates]

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "bpenRows": len(bpen_rows),
        "moneylineCandidates": len(ml_out),
        "moneylineWithExactBpen": sum(1 for c in ml_out if c.get("exactBpenWhip35Available")),
        "ouCandidates": len(ou_out),
        "ouWithExactBpen": sum(1 for c in ou_out if c.get("exactBpenWhip35Available")),
        "moneylineCandidatesMerged": ml_out,
        "ouCandidatesMerged": ou_out,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 184 MERGE EXACT BPEN WHIP35 INTO BBP SIDECARS",
        "=" * 76,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Bpen rows: {len(bpen_rows)}",
        f"Moneyline candidates: {len(ml_out)}",
        f"Moneyline with exact Bpen: {out['moneylineWithExactBpen']}",
        f"O/U candidates: {len(ou_out)}",
        f"O/U with exact Bpen: {out['ouWithExactBpen']}",
        "",
        "Moneyline preview:",
    ]

    for c in ml_out[:10]:
        lines.append(
            f"- {c.get('moneylineBaseballPredGrade')} | {c.get('pick')} | {c.get('game')} | "
            f"AwayBpen={c.get('away_Bpen_WHIP_35_exact','')} HomeBpen={c.get('home_Bpen_WHIP_35_exact','')}"
        )

    lines += ["", "O/U preview:"]
    for c in ou_out[:10]:
        lines.append(
            f"- {c.get('battingAdjustedV2Grade')} | {c.get('pick')} | {c.get('game')} | "
            f"AwayBpen={c.get('away_Bpen_WHIP_35_exact','')} HomeBpen={c.get('home_Bpen_WHIP_35_exact','')}"
        )

    lines += ["", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
