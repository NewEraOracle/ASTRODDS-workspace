from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, json, re, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-253-strict-price-extraction-upgrade-latest.json"
REPORT = REPORTS / "253_strict_price_extraction_upgrade_report.txt"

SOURCE_FILES = [
    ASTRO / "ASTRODDS-289-best-price-line-shopping-latest.csv",
    ASTRO / "ASTRODDS-292-calibrated-candidate-board-latest.csv",
    ASTRO / "ASTRODDS-267-source-first-official-gate-latest.csv",
    ASTRO / "ASTRODDS-266-source-model-market-bridge-latest.csv",
    ASTRO / "ASTRODDS-255-schedule-first-full-slate-bridge-latest.csv",
    ASTRO / "ASTRODDS-273-market-moneyline-sources-latest.csv",
    ASTRO / "ASTRODDS-281-credit-aware-market-fetch-latest.csv",
    ASTRO / "ASTRODDS-299-safe-best-price-line-shopping-latest.csv",
]

TEAM_ALIASES = {
    "athletics": "Athletics", "oakland athletics": "Athletics", "sacramento athletics": "Athletics",
    "la angels": "Los Angeles Angels", "los angeles angels": "Los Angeles Angels",
    "ny yankees": "New York Yankees", "new york yankees": "New York Yankees",
    "ny mets": "New York Mets", "new york mets": "New York Mets",
    "st louis cardinals": "St. Louis Cardinals", "st. louis cardinals": "St. Louis Cardinals",
}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def fnum(v):
    if v is None:
        return None
    s = str(v).strip().replace("%","").replace("$","").replace("+","").replace(",", ".")
    if not s:
        return None
    try:
        x = float(s)
        if 1 < x <= 100:
            return x / 100.0
        return x
    except Exception:
        return None

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
        return round(100 / (odds + 100), 6)
    if odds <= -100:
        return round(abs(odds) / (abs(odds) + 100), 6)
    return None

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

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

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
            if away and home:
                status = (g.get("status") or {}).get("detailedState", "") or (g.get("status") or {}).get("abstractGameState", "")
                games.append({
                    "awayTeam": away,
                    "homeTeam": home,
                    "game": f"{away} @ {home}",
                    "liveMlbStatus": status,
                    "gameDate": g.get("gameDate",""),
                    "gamePk": g.get("gamePk",""),
                })
    return today, games

def text(row):
    return " ".join(str(v or "") for v in row.values())

def has_game(row, away, home):
    t = norm(text(row))
    return norm(away) in t and norm(home) in t

def team_side_score(row, team):
    team_n = norm(team)
    score = 0
    matched_cols = []

    for k,v in row.items():
        kn = norm(k)
        vn = norm(v)
        if team_n and team_n in vn:
            if any(x in kn for x in ["pick","team","selection","side","outcome","candidate","bet","winner","name"]):
                score += 5
                matched_cols.append(k)
            else:
                score += 1

    return score, matched_cols

def extract_row_price(row):
    # Strong team-row generic price columns. Do not accept model probability as price.
    price_cols = [
        "price","marketprice","currentprice","bestprice","bestmarketprice","polymarketprice",
        "entry","entryprice","lineprice","impliedprobability","marketimpliedprobability",
        "decimalprice","probprice"
    ]
    for k,v in row.items():
        kn = norm(k)
        if kn in price_cols or (("price" in kn or "implied" in kn or "entry" in kn) and "model" not in kn and "confidence" not in kn):
            val = fnum(v)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k, "generic_price_on_explicit_team_row"

    for k,v in row.items():
        kn = norm(k)
        if "american" in kn or kn in ("odds","moneylineodds","moneyline"):
            prob = american_to_prob(v)
            if prob is not None and 0.01 <= prob <= 0.99:
                return prob, k, "american_odds_on_explicit_team_row"

    return None, "", ""

def extract_team_named_price(row, team):
    team_n = norm(team)
    for k,v in row.items():
        kn = norm(k)
        if team_n in kn and any(x in kn for x in ["price","odds","implied","market","entry"]):
            val = fnum(v)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k, "team_named_column"
            prob = american_to_prob(v)
            if prob is not None and 0.01 <= prob <= 0.99:
                return prob, k, "team_named_american_column"
    return None, "", ""

def find_price_for_side(game, team):
    candidates = []
    for src in SOURCE_FILES:
        rows = read_csv(src)
        if not rows:
            continue
        for row in rows:
            if not has_game(row, game["awayTeam"], game["homeTeam"]):
                continue

            # 1. Team-named columns can be used even if row is game-level.
            val, col, mode = extract_team_named_price(row, team)
            if val is not None:
                candidates.append((10, val, src, col, mode, row))
                continue

            # 2. Generic price only if the row is explicitly for that team.
            score, cols = team_side_score(row, team)
            if score >= 5:
                val, col, mode = extract_row_price(row)
                if val is not None:
                    candidates.append((score, val, src, col, mode + f";teamCols={cols}", row))

    if not candidates:
        return None, "", "", "", 0

    candidates.sort(key=lambda x: (-x[0], str(x[2])))
    score, val, src, col, mode, row = candidates[0]
    return val, str(src), col, mode, len(candidates)

def extract_model_from_existing(row):
    val = row.get("modelProbability")
    if val is None:
        return None
    return fnum(val)

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    schedule_date, games = fetch_schedule()
    old = load_json(BOARD_JSON)
    old_rows = old.get("moneylineBoard", []) if isinstance(old, dict) else []
    old_by_pick_game = {(norm(r.get("pick","")), norm(r.get("game",""))): r for r in old_rows}

    new_rows = []
    upgraded_prices = 0
    kept_prices = 0

    for g in games:
        for team in [g["awayTeam"], g["homeTeam"]]:
            key = (norm(team), norm(g["game"]))
            old_r = dict(old_by_pick_game.get(key, {}))
            old_price = fnum(old_r.get("price"))
            new_price, src, col, mode, hits = find_price_for_side(g, team)

            if new_price is not None:
                final_price = new_price
                price_source = src
                price_col = col
                price_mode = mode
                if old_price is None:
                    upgraded_prices += 1
                else:
                    kept_prices += 1
            else:
                final_price = old_price
                price_source = old_r.get("priceSourceFile", "")
                price_col = old_r.get("priceSourceColumn", "")
                price_mode = old_r.get("priceSourceMode", "old_or_missing")

            model = extract_model_from_existing(old_r)
            edge = None
            if final_price is not None and model is not None:
                edge = round((model - final_price) * 100, 2)

            new_rows.append({
                **old_r,
                "pick": team,
                "game": g["game"],
                "awayTeam": g["awayTeam"],
                "homeTeam": g["homeTeam"],
                "price": final_price,
                "modelProbability": model,
                "currentEdgePct": edge,
                "edgePct": edge,
                "liveMlbStatus": g["liveMlbStatus"],
                "mlbStatus": g["liveMlbStatus"],
                "liveGameDate": g["gameDate"],
                "liveGamePk": g["gamePk"],
                "priceSourceFile": price_source,
                "priceSourceColumn": price_col,
                "priceSourceMode": price_mode,
                "priceCandidateHits": hits,
                "strictPriceUpgrade": True,
                "telegramEligible": False,
            })

    # Hard sanity: if both sides still have the same price from same source/column/mode, clear price.
    cleared = 0
    by_game = {}
    for r in new_rows:
        by_game.setdefault(norm(r["game"]), []).append(r)
    for group in by_game.values():
        if len(group) == 2:
            a,b = group
            if a.get("price") is not None and b.get("price") is not None and abs(float(a["price"]) - float(b["price"])) < 1e-9:
                if a.get("priceSourceFile") == b.get("priceSourceFile") and a.get("priceSourceColumn") == b.get("priceSourceColumn"):
                    for r in group:
                        r["price"] = None
                        r["currentEdgePct"] = None
                        r["edgePct"] = None
                        r["priceSourceMode"] = "cleared_same_price_both_sides"
                    cleared += 2

    rows_with_price = sum(1 for r in new_rows if r.get("price") is not None)
    rows_with_model = sum(1 for r in new_rows if r.get("modelProbability") is not None)
    rows_with_edge = sum(1 for r in new_rows if r.get("currentEdgePct") is not None)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scheduleDateET": schedule_date,
        "rows": len(new_rows),
        "rowsWithPrice": rows_with_price,
        "rowsWithModel": rows_with_model,
        "rowsWithEdge": rows_with_edge,
        "upgradedPrices": upgraded_prices,
        "keptPrices": kept_prices,
        "clearedDuplicatePrices": cleared,
        "moneylineBoard": new_rows,
        "rule": "Strict price upgrade uses team-named columns or explicit team rows only. Same source/column duplicate side prices are cleared.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(new_rows), "moneylineBoard": new_rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 253 STRICT PRICE EXTRACTION UPGRADE",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        f"Schedule date ET: {schedule_date}",
        "",
        f"Rows: {len(new_rows)}",
        f"Rows with price: {rows_with_price}",
        f"Rows with model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Upgraded prices: {upgraded_prices}",
        f"Kept prices: {kept_prices}",
        f"Cleared duplicate prices: {cleared}",
        "",
        "Board:",
    ]
    for r in new_rows:
        lines.append(
            f"- {r['pick']} | {r['game']} | price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct')} | "
            f"status={r.get('liveMlbStatus')} | priceMode={r.get('priceSourceMode')} | source={Path(r.get('priceSourceFile','')).name if r.get('priceSourceFile') else ''} | col={r.get('priceSourceColumn','')}"
        )

    lines += ["", f"JSON: {OUT_JSON}", "Rule: no fake games, no copied same-side prices."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
