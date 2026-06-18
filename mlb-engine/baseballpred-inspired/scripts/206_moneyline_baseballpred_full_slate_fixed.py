from pathlib import Path
from datetime import datetime, timezone
import csv, json, re, math

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_CLEAN_BOARD = ASTRO / "ASTRODDS-full-slate-game-board-clean-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-full-slate-fixed-latest.json"
REPORT = REPORTS / "206_moneyline_baseballpred_full_slate_fixed_report.txt"

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

STATUS_ORDER = {"OFFICIAL": 0, "A_PAPER": 1, "REVIEW": 2, "WATCH": 3, "BLOCKED": 4, "NO_BET": 5}

PRICE_FILES = [
    ASTRO / "ASTRODDS-mlb-odds-open-close-from-snapshots.csv",
    ASTRO / "ASTRODDS-mlb-odds-snapshot-ledger.csv",
    ASTRO / "ASTRODDS-historical-market-lines-template.csv",
]

BBP_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json"
PUBLIC_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"

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
    try:
        s = str(v).strip().replace("%", "").replace("+", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

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

def first(row, keys, default=""):
    for k in keys:
        if isinstance(row, dict) and k in row and str(row.get(k, "")).strip() != "":
            return row.get(k)
    return default

def flatten(obj):
    out = []
    if isinstance(obj, list):
        for x in obj:
            out.extend(flatten(x))
    elif isinstance(obj, dict):
        if (obj.get("game") or obj.get("Game") or obj.get("matchup")) and any(k in obj for k in ["pick", "Pick", "team", "selection", "decision", "grade", "score"]):
            out.append(obj)
        for v in obj.values():
            out.extend(flatten(v))
    return out

def american_to_prob(x):
    if x >= 100:
        return 100.0 / (x + 100.0)
    if x <= -100:
        return abs(x) / (abs(x) + 100.0)
    return None

def parse_market_price(v):
    x = fnum(v, None)
    if x is None:
        return None
    if 0.01 <= x <= 0.99:
        return x
    if x >= 100 or x <= -100:
        return american_to_prob(x)
    if 1.01 <= x <= 20:
        return 1.0 / x
    return None

def safe_model_probability(v):
    x = fnum(v, None)
    if x is None:
        return None
    if x > 1 and x <= 100:
        x = x / 100.0
    if x < 0.02 or x > 0.98:
        return None
    return x

def score_from_edge(model, price, edge, bbp_score=None):
    if bbp_score is not None:
        return round(float(bbp_score), 2)
    if model is None:
        return 0
    score = model * 100
    if edge is not None:
        score += edge * 100
    return round(max(0, min(99, score)), 2)

def status_from_bbp_score(score):
    if score is None:
        return "NO_BET"
    if score >= 90:
        return "A_PAPER"
    if score >= 75:
        return "REVIEW"
    if score >= 55:
        return "WATCH"
    return "NO_BET"

def status_from_edge(edge):
    if edge is None:
        return "NO_BET"
    if edge >= 0.12:
        return "REVIEW"
    if edge >= 0.06:
        return "WATCH"
    return "NO_BET"

def build_price_index():
    idx = {}
    accepted = []
    rejected = []
    for src in PRICE_FILES:
        for r in read_csv(src):
            market_text = norm(first(r, ["market", "marketType", "type", "outcomeType", "market_key"], ""))
            if market_text and not any(x in market_text for x in ["moneyline", "h2h", "head to head"]):
                continue

            game = first(r, ["game", "Game", "matchup"])
            away = first(r, ["awayTeam", "away_team", "away"])
            home = first(r, ["homeTeam", "home_team", "home"])
            team = first(r, ["pick", "Pick", "team", "outcome", "selection", "name", "outcomeName"])

            if not game and away and home:
                game = f"{away} @ {home}"

            key = (game_key(game, away, home), team_key(team))
            if not key[0] or not key[1]:
                continue

            raw = None
            for k in ["close_price", "closePrice", "price", "Price", "marketPrice", "last_price", "open_price", "odds", "americanOdds", "decimalPrice"]:
                if k in r and str(r.get(k, "")).strip() != "":
                    raw = r.get(k)
                    break

            price = parse_market_price(raw)
            if price is None:
                if raw not in (None, "") and len(rejected) < 20:
                    rejected.append({"source": src.name, "game": game, "team": team, "raw": raw})
                continue

            idx[key] = {"price": price, "source": src.name, "raw": raw}
            if len(accepted) < 20:
                accepted.append({"source": src.name, "game": game, "team": team, "raw": raw, "price": price})
    return idx, accepted, rejected

def extract_public_rows():
    data = load_json(PUBLIC_JSON)
    rows = []
    for bucket, status in [
        ("aPick", "OFFICIAL"),
        ("aPicks", "OFFICIAL"),
        ("valueLean", "REVIEW"),
        ("valueLeans", "REVIEW"),
        ("actionLean", "WATCH"),
        ("actionLeans", "WATCH"),
    ]:
        vals = data.get(bucket, [])
        if not isinstance(vals, list):
            continue
        for r in vals:
            rows.append((r, status, bucket))
    return rows

def extract_bbp_rows():
    data = load_json(BBP_JSON)
    rows = data.get("candidates", []) if isinstance(data, dict) else []
    if not rows:
        rows = flatten(data)
    return rows

def apply_public(public_rows, ml):
    for r, status, bucket in public_rows:
        game = first(r, ["game", "Game", "matchup"])
        away, home = parse_game(game)
        pick = first(r, ["pick", "Pick", "team", "selection"])
        key = (game_key(game, away, home), team_key(pick))
        if key not in ml:
            continue

        price = parse_market_price(first(r, ["price", "Price", "market", "Market", "marketPrice"], ""))
        model = safe_model_probability(first(r, ["modelProbability", "modelProb", "probability", "Model"], ""))
        edge = fnum(first(r, ["edgePct", "edge", "Edge"], ""), None)

        row = ml[key]
        row["status"] = status
        row["telegramEligible"] = status == "OFFICIAL"
        row["grade"] = "A" if status == "OFFICIAL" else status
        row["mainReason"] = f"Public board category: {bucket}"
        if price is not None:
            row["price"] = price
        if model is not None:
            row["modelProbability"] = model
        if edge is not None:
            row["edgePct"] = edge
        row["baseballPredScore"] = score_from_edge(row.get("modelProbability") if row.get("modelProbability") != "" else None, row.get("price") if row.get("price") != "" else None, row.get("edgePct") if row.get("edgePct") != "" else None)

def apply_bbp(bbp_rows, ml):
    for r in bbp_rows:
        game = first(r, ["game", "Game", "matchup"])
        away, home = parse_game(game)
        pick = first(r, ["pick", "Pick", "team", "selection"])
        key = (game_key(game, away, home), team_key(pick))
        if key not in ml:
            continue

        score = fnum(first(r, ["score", "Score", "baseballPredScore", "moneylineBaseballPredScore"], ""), None)
        status = status_from_bbp_score(score)
        row = ml[key]

        if STATUS_ORDER.get(row["status"], 9) > STATUS_ORDER.get(status, 9):
            row["status"] = status
            row["telegramEligible"] = False
            row["grade"] = first(r, ["grade", "Grade", "decision"], status)
            row["mainReason"] = "BaseballPred Moneyline sidecar likes this pick."
            row["riskReason"] = "Paper/dashboard only until sidecar proves better than live 135."

        if score is not None and score > fnum(row.get("baseballPredScore"), 0):
            row["baseballPredScore"] = round(score, 2)

def apply_prices(price_idx, ml):
    priced = 0
    for key, row in ml.items():
        if row.get("price") not in ("", None):
            continue
        p = price_idx.get(key)
        if p:
            row["price"] = p["price"]
            row["priceSource"] = p["source"]
            priced += 1
    return priced

def apply_edge_scores(ml):
    edge_scored = 0
    for key, row in ml.items():
        model = row.get("modelProbability")
        price = row.get("price")
        if model not in ("", None) and price not in ("", None):
            edge = fnum(model) - fnum(price)
            row["edgePct"] = edge
            if row["status"] == "NO_BET":
                row["status"] = status_from_edge(edge)
                if row["status"] != "NO_BET":
                    row["mainReason"] = "Full slate Moneyline edge found using safe price/model parse."
                    row["riskReason"] = "Dashboard only. Not Telegram unless live 135 qualifies."
            if fnum(row.get("baseballPredScore"), 0) <= 0:
                row["baseballPredScore"] = score_from_edge(fnum(model), fnum(price), edge)
            edge_scored += 1
    return edge_scored

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    clean = load_json(IN_CLEAN_BOARD)
    board_rows = clean.get("gameBoard", []) if isinstance(clean, dict) else []

    games = {}
    for r in board_rows:
        game = r.get("game", "")
        away = r.get("awayTeam", "")
        home = r.get("homeTeam", "")
        if not away or not home:
            away, home = parse_game(game)
        gk = game_key(game, away, home)
        if gk and gk not in games:
            games[gk] = {"game": game, "awayTeam": away, "homeTeam": home}

    ml = {}
    for g in games.values():
        for team, side in [(g["awayTeam"], "away"), (g["homeTeam"], "home")]:
            if not team:
                continue
            key = (game_key(g["game"], g["awayTeam"], g["homeTeam"]), team_key(team))
            ml[key] = {
                "rank": None,
                "status": "NO_BET",
                "marketType": "MONEYLINE",
                "pick": team,
                "game": g["game"],
                "awayTeam": g["awayTeam"],
                "homeTeam": g["homeTeam"],
                "line": "",
                "price": "",
                "modelProbability": "",
                "edgePct": "",
                "edgeRuns": "",
                "baseballPredScore": 0,
                "grade": "NO_BET",
                "telegramEligible": False,
                "mainReason": "Game scanned, but no clean BaseballPred Moneyline edge.",
                "riskReason": "No safe price/model/BBP score strong enough for this side.",
                "sourceFilesUsed": [],
                "side": side,
            }

    price_idx, accepted_prices, rejected_prices = build_price_index()
    apply_prices(price_idx, ml)
    apply_public(extract_public_rows(), ml)
    apply_bbp(extract_bbp_rows(), ml)
    edge_scored = apply_edge_scores(ml)

    ml_rows = list(ml.values())
    ml_rows.sort(key=lambda r: (STATUS_ORDER.get(r.get("status", "NO_BET"), 9), -fnum(r.get("baseballPredScore"), 0)))
    for i, r in enumerate(ml_rows, 1):
        r["rank"] = i

    counts = {}
    for r in ml_rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "games": len(games),
        "moneylineRows": len(ml_rows),
        "priceIndexRows": len(price_idx),
        "edgeScoredRows": edge_scored,
        "counts": counts,
        "acceptedPricePreview": accepted_prices,
        "rejectedPricePreview": rejected_prices,
        "moneylineBoard": ml_rows,
        "rule": "Dashboard only. Safe Moneyline BaseballPred board. No Telegram send.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 206 MONEYLINE BASEBALLPRED FULL SLATE FIXED",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Games: {out['games']}",
        f"Moneyline rows: {out['moneylineRows']}",
        f"Price index rows: {out['priceIndexRows']}",
        f"Edge scored rows: {out['edgeScoredRows']}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "Top Moneyline board:"]
    for r in ml_rows[:40]:
        lines.append(
            f"- #{r['rank']} | {r['status']} | {r['pick']} | {r['game']} | "
            f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('edgePct')} | "
            f"score={r.get('baseballPredScore')} | telegram={r.get('telegramEligible')} | {r.get('mainReason')}"
        )
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")

    lines += ["", "Accepted price preview:"]
    for p in accepted_prices[:10]:
        lines.append(f"- {p}")
    lines += ["", "Rejected unsafe price preview:"]
    for p in rejected_prices[:10]:
        lines.append(f"- {p}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
