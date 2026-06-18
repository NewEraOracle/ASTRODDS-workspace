from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, json, re, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_BOARD = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-source-first-strict-team-side-board-latest.json"
REPORT = REPORTS / "249_source_first_strict_team_side_board_report.txt"

SOURCES = [
    ASTRO / "ASTRODDS-289-best-price-line-shopping-latest.csv",
    ASTRO / "ASTRODDS-292-calibrated-candidate-board-latest.csv",
    ASTRO / "ASTRODDS-267-source-first-official-gate-latest.csv",
    ASTRO / "ASTRODDS-266-source-model-market-bridge-latest.csv",
    ASTRO / "ASTRODDS-255-schedule-first-full-slate-bridge-latest.csv",
]

TEAM_ALIASES = {
    "athletics": "Athletics", "oakland athletics": "Athletics", "sacramento athletics": "Athletics",
    "la angels": "Los Angeles Angels", "los angeles angels": "Los Angeles Angels",
    "la dodgers": "Los Angeles Dodgers", "los angeles dodgers": "Los Angeles Dodgers",
    "ny yankees": "New York Yankees", "new york yankees": "New York Yankees",
    "ny mets": "New York Mets", "new york mets": "New York Mets",
    "st louis cardinals": "St. Louis Cardinals", "st. louis cardinals": "St. Louis Cardinals",
}

TEAM_COLS = ["pick","team","selection","side","outcome","marketOutcome","market_outcome","candidate","recommendedPick","recommended_pick","bet","betTeam","bet_team"]
GAME_COLS = ["game","matchup","event","name","title","market","marketTitle","market_title"]
PRICE_COLS = ["price","marketPrice","market_price","currentPrice","current_price","bestPrice","best_price","impliedProbability","implied_probability","marketProbability","market_probability","polymarketPrice","polymarket_price","oddsPrice","odds_price","linePrice","line_price","entry","entryPrice","entry_price"]
MODEL_COLS = ["modelProbability","model_probability","probability","calibratedProbability","calibrated_probability","calibratedConfidence","calibrated_confidence","confidence","modelProb","model_prob","winProbability","win_probability"]

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def canon(s):
    raw = str(s or "").strip()
    return TEAM_ALIASES.get(norm(raw), raw)

def fnum(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%","").replace("+","").replace("$","").replace(",", ".")
    if not s:
        return default
    try:
        x = float(s)
        if 1.0 < x <= 100.0:
            return x / 100.0
        return x
    except Exception:
        return default

def american_to_prob(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    try:
        odds = float(s)
    except Exception:
        return None
    if odds >= 100:
        return round(100.0/(odds+100.0), 6)
    if odds <= -100:
        return round(abs(odds)/(abs(odds)+100.0), 6)
    return None

def fetch_schedule():
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            teams = g.get("teams", {})
            away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
            home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
            if not away or not home:
                continue
            status = (g.get("status") or {}).get("detailedState", "") or (g.get("status") or {}).get("abstractGameState", "")
            games.append({"awayTeam": away, "homeTeam": home, "game": f"{away} @ {home}", "liveMlbStatus": status, "gameDate": g.get("gameDate",""), "gamePk": g.get("gamePk","")})
    return today, games

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel
            return [{str(k or "").strip(): v for k,v in row.items()} for row in csv.DictReader(f, dialect=dialect)]
    except Exception:
        return []

def row_text(row):
    return " ".join(str(v or "") for v in row.values())

def has_game(row, away, home):
    txt = norm(row_text(row))
    return norm(away) in txt and norm(home) in txt

def explicit_team_match(row, team):
    team_n = norm(team)

    # Strong match: known pick/team/selection columns equal this team.
    for k,v in row.items():
        if norm(k) in [norm(c) for c in TEAM_COLS]:
            if norm(v) == team_n or team_n in norm(v):
                return True, k

    # Medium match: team appears in a side/outcome-ish column.
    for k,v in row.items():
        kn = norm(k)
        if any(x in kn for x in ["pick","team","selection","side","outcome","candidate","bet"]):
            if team_n in norm(v):
                return True, k

    return False, ""

def col_value(row, col_names):
    wanted = [norm(c) for c in col_names]
    for k,v in row.items():
        if norm(k) in wanted:
            val = fnum(v, None)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k
    return None, ""

def team_named_value(row, team, tokens):
    team_n = norm(team)
    for k,v in row.items():
        kn = norm(k)
        val = fnum(v, None)
        if val is not None and 0.01 <= val <= 0.99 and team_n in kn and any(t in kn for t in tokens):
            return val, k
    return None, ""

def extract_price_strict(row, team, explicit):
    # If columns are named for exact team, OK.
    val, col = team_named_value(row, team, ["price","prob","implied","market","entry"])
    if val is not None:
        return val, col, "team_named_price_column"

    # Generic price is accepted ONLY when row is explicitly for that team.
    if explicit:
        val, col = col_value(row, PRICE_COLS)
        if val is not None:
            return val, col, "explicit_team_row_generic_price"

        for k,v in row.items():
            if any(x in norm(k) for x in ["american","odds","moneyline"]):
                prob = american_to_prob(v)
                if prob is not None and 0.01 <= prob <= 0.99:
                    return prob, k, "explicit_team_row_american_odds"

    return None, "", ""

def extract_model_strict(row, team, explicit):
    val, col = team_named_value(row, team, ["model","prob","confidence"])
    if val is not None:
        return val, col, "team_named_model_column"

    if explicit:
        val, col = col_value(row, MODEL_COLS)
        if val is not None:
            return val, col, "explicit_team_row_generic_model"

    return None, "", ""

def find_side(game, team, sources):
    result = {"price": None, "priceSourceFile": "", "priceSourceColumn": "", "priceSourceMode": "", "modelProbability": None, "modelSourceFile": "", "modelSourceColumn": "", "modelSourceMode": ""}
    inspected_matches = 0
    explicit_matches = 0

    for src in sources:
        for row in read_csv(src):
            if not has_game(row, game["awayTeam"], game["homeTeam"]):
                continue
            inspected_matches += 1
            explicit, explicit_col = explicit_team_match(row, team)
            if explicit:
                explicit_matches += 1

            if result["price"] is None:
                price, col, mode = extract_price_strict(row, team, explicit)
                if price is not None:
                    result["price"] = price
                    result["priceSourceFile"] = str(src)
                    result["priceSourceColumn"] = col
                    result["priceSourceMode"] = mode

            if result["modelProbability"] is None:
                model, col, mode = extract_model_strict(row, team, explicit)
                if model is not None:
                    result["modelProbability"] = model
                    result["modelSourceFile"] = str(src)
                    result["modelSourceColumn"] = col
                    result["modelSourceMode"] = mode

            if result["price"] is not None and result["modelProbability"] is not None:
                result["inspectedGameRows"] = inspected_matches
                result["explicitTeamRows"] = explicit_matches
                return result

    result["inspectedGameRows"] = inspected_matches
    result["explicitTeamRows"] = explicit_matches
    return result

def inverse_fill_models(rows):
    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r["game"]), []).append(r)
    fills = 0
    for group in by_game.values():
        modeled = [r for r in group if r.get("modelProbability") is not None]
        missing = [r for r in group if r.get("modelProbability") is None]
        if len(modeled) == 1 and len(missing) == 1:
            m = modeled[0]["modelProbability"]
            missing[0]["modelProbability"] = round(1.0 - m, 6)
            missing[0]["modelSourceFile"] = "two_side_inverse_from_opponent"
            missing[0]["modelSourceColumn"] = modeled[0]["pick"]
            missing[0]["modelSourceMode"] = "two_side_inverse_from_opponent"
            fills += 1
    return fills

def sanity_clear_duplicate_sides(rows):
    # If both sides of a game have identical price/model from same generic source, clear it.
    # This prevents fake duplicate side values like both teams 0.537 / 0.485.
    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r["game"]), []).append(r)
    cleared = 0
    for group in by_game.values():
        if len(group) != 2:
            continue
        a,b = group
        if a.get("price") is not None and b.get("price") is not None and abs(a["price"] - b["price"]) < 1e-9:
            if a.get("priceSourceColumn") == b.get("priceSourceColumn"):
                for r in group:
                    r["price"] = None
                    r["priceSourceFile"] = ""
                    r["priceSourceColumn"] = ""
                    r["priceSourceMode"] = "cleared_duplicate_same_side_price"
                cleared += 2
        if a.get("modelProbability") is not None and b.get("modelProbability") is not None and abs(a["modelProbability"] - b["modelProbability"]) < 1e-9:
            if a.get("modelSourceColumn") == b.get("modelSourceColumn"):
                for r in group:
                    r["modelProbability"] = None
                    r["modelSourceFile"] = ""
                    r["modelSourceColumn"] = ""
                    r["modelSourceMode"] = "cleared_duplicate_same_side_model"
                cleared += 2
    return cleared

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    date, games = fetch_schedule()
    sources = [p for p in SOURCES if p.exists()]

    rows = []
    for g in games:
        for team in [g["awayTeam"], g["homeTeam"]]:
            found = find_side(g, team, sources)
            rows.append({
                "pick": team,
                "game": g["game"],
                "awayTeam": g["awayTeam"],
                "homeTeam": g["homeTeam"],
                "price": found["price"],
                "modelProbability": found["modelProbability"],
                "currentEdgePct": None,
                "edgePct": None,
                "liveMlbStatus": g["liveMlbStatus"],
                "mlbStatus": g["liveMlbStatus"],
                "liveGameDate": g["gameDate"],
                "liveGamePk": g["gamePk"],
                **found,
                "sourceFirstStrictTeamSide": True,
                "telegramEligible": False,
            })

    duplicate_cleared = sanity_clear_duplicate_sides(rows)
    model_fills = inverse_fill_models(rows)

    for r in rows:
        if r.get("price") is not None and r.get("modelProbability") is not None:
            r["currentEdgePct"] = round((r["modelProbability"] - r["price"]) * 100.0, 2)
            r["edgePct"] = r["currentEdgePct"]

    price_rows = sum(1 for r in rows if r.get("price") is not None)
    model_rows = sum(1 for r in rows if r.get("modelProbability") is not None)
    edge_rows = sum(1 for r in rows if r.get("currentEdgePct") is not None)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scheduleDateET": date,
        "officialGames": len(games),
        "rows": len(rows),
        "rowsWithPrice": price_rows,
        "rowsWithModel": model_rows,
        "rowsWithEdge": edge_rows,
        "twoSideModelFills": model_fills,
        "duplicateSideValuesCleared": duplicate_cleared,
        "sourcesUsed": [str(p) for p in sources],
        "moneylineBoard": rows,
        "rule": "Strict team-side source-first board. Generic price/model columns require explicit team row. Duplicate same-side values are cleared.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    OUT_BOARD.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(rows), "moneylineBoard": rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 249 SOURCE-FIRST STRICT TEAM-SIDE MONEYLINE BOARD",
        "="*82,
        f"Generated UTC: {out['generatedAt']}",
        f"Schedule date ET: {date}",
        "",
        f"Official games: {len(games)}",
        f"Rows: {len(rows)}",
        f"Rows with price: {price_rows}",
        f"Rows with model: {model_rows}",
        f"Rows with edge: {edge_rows}",
        f"Two-side model fills: {model_fills}",
        f"Duplicate side values cleared: {duplicate_cleared}",
        "",
        "Board:",
    ]
    for r in rows:
        lines.append(
            f"- {r['pick']} | {r['game']} | price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct')} | "
            f"status={r.get('liveMlbStatus')} | priceMode={r.get('priceSourceMode','')} | modelMode={r.get('modelSourceMode','')} | explicitRows={r.get('explicitTeamRows')}"
        )
    lines += ["", f"JSON: {OUT_JSON}", "Rule: no same generic value can be assigned to both teams."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
