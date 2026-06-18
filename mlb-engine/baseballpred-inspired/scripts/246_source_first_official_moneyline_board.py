from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, json, re, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_BOARD = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-source-first-moneyline-board-latest.json"
REPORT = REPORTS / "246_source_first_official_moneyline_board_report.txt"

# Preferred files discovered by the trace reports.
PREFERRED_SOURCES = [
    ASTRO / "ASTRODDS-289-best-price-line-shopping-latest.csv",
    ASTRO / "ASTRODDS-292-calibrated-candidate-board-latest.csv",
    ASTRO / "ASTRODDS-267-source-first-official-gate-latest.csv",
    ASTRO / "ASTRODDS-266-source-model-market-bridge-latest.csv",
    ASTRO / "ASTRODDS-255-schedule-first-full-slate-bridge-latest.csv",
]

TEAM_ALIASES = {
    "athletics": "Athletics",
    "oakland athletics": "Athletics",
    "sacramento athletics": "Athletics",
    "la angels": "Los Angeles Angels",
    "los angeles angels": "Los Angeles Angels",
    "la dodgers": "Los Angeles Dodgers",
    "los angeles dodgers": "Los Angeles Dodgers",
    "ny yankees": "New York Yankees",
    "new york yankees": "New York Yankees",
    "ny mets": "New York Mets",
    "new york mets": "New York Mets",
    "st louis cardinals": "St. Louis Cardinals",
    "st. louis cardinals": "St. Louis Cardinals",
}

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
    s = str(v).strip().replace("%", "").replace("+", "").replace(",", ".").replace("$", "")
    if not s:
        return default
    try:
        x = float(s)
        if x > 1.0 and x <= 100.0:
            # Some files store probability as percent.
            return x / 100.0
        return x
    except Exception:
        return default

def pct_to_price_from_american(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    try:
        odds = float(s)
    except Exception:
        return None
    # Treat +/- American odds as implied probability.
    if odds >= 100:
        return round(100.0 / (odds + 100.0), 6)
    if odds <= -100:
        return round(abs(odds) / (abs(odds) + 100.0), 6)
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
            games.append({
                "awayTeam": away,
                "homeTeam": home,
                "game": f"{away} @ {home}",
                "liveMlbStatus": status,
                "gameDate": g.get("gameDate", ""),
                "gamePk": g.get("gamePk", ""),
            })
    return today, games

def read_csv_rows(path):
    if not path.exists():
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                rows.append({str(k or "").strip(): v for k, v in row.items()})
    except Exception:
        return []
    return rows

def row_text(row):
    return " ".join(str(v or "") for v in row.values())

def row_matches_game(row, away, home):
    t = norm(row_text(row))
    away_n = norm(away)
    home_n = norm(home)
    return away_n in t and home_n in t

def row_matches_team(row, team):
    return norm(team) in norm(row_text(row))

def extract_price(row, team):
    # First: team-specific probability/price fields.
    team_n = norm(team)
    for k, v in row.items():
        kn = norm(k)
        val = fnum(v, None)
        if val is not None and 0.01 <= val <= 0.99 and team_n in kn and any(x in kn for x in ["price", "prob", "implied", "market"]):
            return val, k

    # Second: generic likely price columns when row itself is team-specific.
    generic_cols = [
        "price", "marketPrice", "market_price", "currentPrice", "current_price",
        "bestPrice", "best_price", "impliedProbability", "implied_probability",
        "marketProbability", "market_probability", "polymarketPrice", "polymarket_price",
        "oddsPrice", "odds_price", "linePrice", "line_price"
    ]
    for k, v in row.items():
        if norm(k) in [norm(c) for c in generic_cols]:
            val = fnum(v, None)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k

    # Third: American odds.
    for k, v in row.items():
        kn = norm(k)
        if any(x in kn for x in ["american", "odds", "moneyline"]):
            val = pct_to_price_from_american(v)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k

    return None, ""

def extract_model(row, team):
    team_n = norm(team)
    for k, v in row.items():
        kn = norm(k)
        val = fnum(v, None)
        if val is not None and 0.01 <= val <= 0.99 and team_n in kn and any(x in kn for x in ["model", "prob", "confidence"]):
            return val, k

    for k, v in row.items():
        kn = norm(k)
        if any(x in kn for x in ["modelprobability", "model probability", "probability", "calibratedconfidence", "confidence"]):
            val = fnum(v, None)
            if val is not None and 0.01 <= val <= 0.99:
                return val, k
    return None, ""

def build_side_from_sources(game, team, sources):
    best = {
        "price": None,
        "priceSourceFile": "",
        "priceSourceColumn": "",
        "modelProbability": None,
        "modelSourceFile": "",
        "modelSourceColumn": "",
    }

    for src in sources:
        rows = read_csv_rows(src)
        if not rows:
            continue
        for row in rows:
            if not row_matches_game(row, game["awayTeam"], game["homeTeam"]):
                continue
            if not row_matches_team(row, team):
                continue

            if best["price"] is None:
                price, col = extract_price(row, team)
                if price is not None:
                    best["price"] = price
                    best["priceSourceFile"] = str(src)
                    best["priceSourceColumn"] = col

            if best["modelProbability"] is None:
                model, col = extract_model(row, team)
                if model is not None:
                    best["modelProbability"] = model
                    best["modelSourceFile"] = str(src)
                    best["modelSourceColumn"] = col

            if best["price"] is not None and best["modelProbability"] is not None:
                return best

    return best

def inverse_fill_models(rows):
    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r["game"]), []).append(r)
    filled = 0
    for game_rows in by_game.values():
        modeled = [r for r in game_rows if r.get("modelProbability") is not None]
        missing = [r for r in game_rows if r.get("modelProbability") is None]
        if len(modeled) == 1 and missing:
            m = modeled[0]["modelProbability"]
            for r in missing:
                r["modelProbability"] = round(1.0 - m, 6)
                r["modelSourceFile"] = "two_side_inverse_from_opponent"
                r["modelSourceColumn"] = modeled[0].get("pick", "")
                filled += 1
    return filled

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    schedule_date, games = fetch_schedule()
    sources = [p for p in PREFERRED_SOURCES if p.exists()]

    rows = []
    for g in games:
        for team in [g["awayTeam"], g["homeTeam"]]:
            found = build_side_from_sources(g, team, sources)
            price = found["price"]
            model = found["modelProbability"]
            edge = None
            if price is not None and model is not None:
                edge = round((model - price) * 100.0, 2)

            rows.append({
                "pick": team,
                "game": g["game"],
                "awayTeam": g["awayTeam"],
                "homeTeam": g["homeTeam"],
                "price": price,
                "modelProbability": model,
                "currentEdgePct": edge,
                "edgePct": edge,
                "liveMlbStatus": g["liveMlbStatus"],
                "mlbStatus": g["liveMlbStatus"],
                "liveGameDate": g["gameDate"],
                "liveGamePk": g["gamePk"],
                "priceSourceFile": found["priceSourceFile"],
                "priceSourceColumn": found["priceSourceColumn"],
                "modelSourceFile": found["modelSourceFile"],
                "modelSourceColumn": found["modelSourceColumn"],
                "sourceFirstBoard": True,
                "telegramEligible": False,
            })

    filled_models = inverse_fill_models(rows)
    for r in rows:
        if r["price"] is not None and r["modelProbability"] is not None:
            r["currentEdgePct"] = round((r["modelProbability"] - r["price"]) * 100.0, 2)
            r["edgePct"] = r["currentEdgePct"]

    price_rows = sum(1 for r in rows if r["price"] is not None)
    model_rows = sum(1 for r in rows if r["modelProbability"] is not None)
    edge_rows = sum(1 for r in rows if r["currentEdgePct"] is not None)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scheduleDateET": schedule_date,
        "officialGames": len(games),
        "rows": len(rows),
        "rowsWithPrice": price_rows,
        "rowsWithModel": model_rows,
        "rowsWithEdge": edge_rows,
        "twoSideModelFills": filled_models,
        "sourcesUsed": [str(p) for p in sources],
        "moneylineBoard": rows,
        "rule": "Source-first board is built from official MLB schedule first, then joins price/model from source files. No stale games allowed.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    # Replace the standard board so downstream scripts use the no-fake official slate.
    (ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json").write_text(json.dumps({
        "generatedAt": out["generatedAt"],
        "moneylineRows": len(rows),
        "moneylineBoard": rows,
        "rule": out["rule"],
    }, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 246 SOURCE-FIRST OFFICIAL MONEYLINE BOARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        f"Schedule date ET: {schedule_date}",
        "",
        f"Official games: {out['officialGames']}",
        f"Moneyline rows: {out['rows']}",
        f"Rows with price: {price_rows}",
        f"Rows with model: {model_rows}",
        f"Rows with edge: {edge_rows}",
        f"Two-side model fills: {filled_models}",
        "",
        "Sources used:",
    ]
    for p in sources:
        lines.append(f"- {p}")

    lines += ["", "Board:"]
    for r in rows:
        lines.append(
            f"- {r['pick']} | {r['game']} | price={r['price']} | model={r['modelProbability']} | "
            f"edge={r['currentEdgePct']} | status={r['liveMlbStatus']} | priceSource={Path(r['priceSourceFile']).name if r['priceSourceFile'] else ''} | modelSource={Path(r['modelSourceFile']).name if r['modelSourceFile'] else ''}"
        )

    lines += ["", f"JSON: {OUT_JSON}", "Rule: official schedule first, no fake games."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
