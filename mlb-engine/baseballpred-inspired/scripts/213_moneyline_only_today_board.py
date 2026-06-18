from pathlib import Path
from datetime import datetime, timezone
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
REPORT = REPORTS / "213_moneyline_only_today_board_report.txt"

PUBLIC_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"
BBP_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json"

PRICE_FILES = [
    ASTRO / "ASTRODDS-mlb-odds-open-close-from-snapshots.csv",
    ASTRO / "ASTRODDS-mlb-odds-snapshot-ledger.csv",
    ASTRO / "ASTRODDS-historical-market-lines-template.csv",
]

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

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

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

def parse_price(v):
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

def status_from_bbp(score):
    if score is None:
        return "NO_BET"
    if score >= 90:
        return "A_PAPER"
    if score >= 75:
        return "REVIEW"
    if score >= 55:
        return "WATCH"
    return "NO_BET"

def build_moneyline_from_prices():
    board = {}
    price_rows = 0

    for src in PRICE_FILES:
        for r in read_csv(src):
            market = norm(first(r, ["market", "marketType", "type", "outcomeType", "market_key"], ""))
            if market and not any(x in market for x in ["moneyline", "h2h", "head to head"]):
                continue

            game = first(r, ["game", "Game", "matchup"])
            away = first(r, ["awayTeam", "away_team", "away"])
            home = first(r, ["homeTeam", "home_team", "home"])
            team = first(r, ["pick", "Pick", "team", "outcome", "selection", "name", "outcomeName"])

            if not game and away and home:
                game = f"{away} @ {home}"
            if not away or not home:
                away, home = parse_game(game)

            gk = game_key(game, away, home)
            tk = team_key(team)
            if not gk or not tk or not team:
                continue

            raw = None
            for k in ["close_price", "closePrice", "price", "Price", "marketPrice", "last_price", "open_price", "odds", "americanOdds", "decimalPrice"]:
                if k in r and str(r.get(k, "")).strip() != "":
                    raw = r.get(k)
                    break

            price = parse_price(raw)
            if price is None:
                continue

            key = (gk, tk)
            if key not in board:
                board[key] = {
                    "rank": None,
                    "status": "NO_BET",
                    "marketType": "MONEYLINE",
                    "pick": canon(team),
                    "game": game,
                    "awayTeam": away,
                    "homeTeam": home,
                    "price": price,
                    "rawPrice": raw,
                    "modelProbability": "",
                    "edgePct": "",
                    "baseballPredScore": 0,
                    "grade": "NO_BET",
                    "telegramEligible": False,
                    "mainReason": "Moneyline market scanned. No clean model edge yet.",
                    "riskReason": "No safe BaseballPred model probability attached to this side.",
                    "sourceFilesUsed": [src.name],
                }
            else:
                board[key]["price"] = price
                board[key]["rawPrice"] = raw
                if src.name not in board[key]["sourceFilesUsed"]:
                    board[key]["sourceFilesUsed"].append(src.name)
            price_rows += 1

    return board, price_rows

def apply_public(board):
    data = load_json(PUBLIC_JSON)
    applied = 0
    buckets = [
        ("aPick", "OFFICIAL"),
        ("aPicks", "OFFICIAL"),
        ("valueLean", "REVIEW"),
        ("valueLeans", "REVIEW"),
        ("actionLean", "WATCH"),
        ("actionLeans", "WATCH"),
    ]

    for bucket, status in buckets:
        rows = data.get(bucket, [])
        if not isinstance(rows, list):
            continue
        for r in rows:
            game = first(r, ["game", "Game", "matchup"])
            away, home = parse_game(game)
            pick = first(r, ["pick", "Pick", "team", "selection"])
            if not pick:
                continue
            key = (game_key(game, away, home), team_key(pick))
            if key not in board:
                board[key] = {
                    "rank": None,
                    "status": status,
                    "marketType": "MONEYLINE",
                    "pick": canon(pick),
                    "game": game,
                    "awayTeam": away,
                    "homeTeam": home,
                    "price": "",
                    "rawPrice": "",
                    "modelProbability": "",
                    "edgePct": "",
                    "baseballPredScore": 0,
                    "grade": "A" if status == "OFFICIAL" else status,
                    "telegramEligible": status == "OFFICIAL",
                    "mainReason": f"Public board category: {bucket}",
                    "riskReason": "",
                    "sourceFilesUsed": [PUBLIC_JSON.name],
                }
            row = board[key]
            row["status"] = status
            row["telegramEligible"] = status == "OFFICIAL"
            row["grade"] = "A" if status == "OFFICIAL" else status
            row["mainReason"] = f"Public board category: {bucket}"
            p = parse_price(first(r, ["price", "Price", "market", "Market", "marketPrice"], ""))
            if p is not None:
                row["price"] = p
            edge = fnum(first(r, ["edgePct", "edge", "Edge"], ""), None)
            if edge is not None:
                row["edgePct"] = edge
                row["baseballPredScore"] = round(50 + edge * 3, 2)
            if PUBLIC_JSON.name not in row["sourceFilesUsed"]:
                row["sourceFilesUsed"].append(PUBLIC_JSON.name)
            applied += 1
    return applied

def apply_bbp(board):
    data = load_json(BBP_JSON)
    rows = data.get("candidates", []) if isinstance(data, dict) else []
    if not rows:
        rows = flatten(data)
    applied = 0

    for r in rows:
        game = first(r, ["game", "Game", "matchup"])
        away, home = parse_game(game)
        pick = first(r, ["pick", "Pick", "team", "selection"])
        if not pick:
            continue
        key = (game_key(game, away, home), team_key(pick))
        score = fnum(first(r, ["score", "Score", "baseballPredScore", "moneylineBaseballPredScore"], ""), None)
        status = status_from_bbp(score)

        if key not in board:
            board[key] = {
                "rank": None,
                "status": status,
                "marketType": "MONEYLINE",
                "pick": canon(pick),
                "game": game,
                "awayTeam": away,
                "homeTeam": home,
                "price": "",
                "rawPrice": "",
                "modelProbability": "",
                "edgePct": "",
                "baseballPredScore": score or 0,
                "grade": first(r, ["grade", "Grade", "decision"], status),
                "telegramEligible": False,
                "mainReason": "BaseballPred Moneyline sidecar likes this pick.",
                "riskReason": "Paper/dashboard only until sidecar proves better than live 135.",
                "sourceFilesUsed": [BBP_JSON.name],
            }
        row = board[key]
        if STATUS_ORDER.get(row["status"], 9) > STATUS_ORDER.get(status, 9):
            row["status"] = status
            row["telegramEligible"] = False
            row["grade"] = first(r, ["grade", "Grade", "decision"], status)
            row["mainReason"] = "BaseballPred Moneyline sidecar likes this pick."
            row["riskReason"] = "Paper/dashboard only until sidecar proves better than live 135."
        if score is not None and score > fnum(row.get("baseballPredScore"), 0):
            row["baseballPredScore"] = round(score, 2)
        if BBP_JSON.name not in row["sourceFilesUsed"]:
            row["sourceFilesUsed"].append(BBP_JSON.name)
        applied += 1
    return applied

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    board, price_rows = build_moneyline_from_prices()
    public_applied = apply_public(board)
    bbp_applied = apply_bbp(board)

    rows = list(board.values())
    rows.sort(key=lambda r: (STATUS_ORDER.get(r.get("status", "NO_BET"), 9), -fnum(r.get("baseballPredScore"), 0), -fnum(r.get("price"), 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    counts = {}
    for r in rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "moneylineRows": len(rows),
        "priceRowsRead": price_rows,
        "publicRowsApplied": public_applied,
        "bbpRowsApplied": bbp_applied,
        "counts": counts,
        "moneylineBoard": rows,
        "rule": "MONEYLINE ONLY. No O/U rows. Dashboard only. Telegram unchanged.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 213 MONEYLINE ONLY TODAY BOARD",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Moneyline rows: {out['moneylineRows']}",
        f"Price rows read: {out['priceRowsRead']}",
        f"Public rows applied: {out['publicRowsApplied']}",
        f"BaseballPred sidecar rows applied: {out['bbpRowsApplied']}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "MONEYLINE BOARD:"]
    for r in rows[:80]:
        lines.append(f"- #{r['rank']} | {r['status']} | {r['pick']} | {r['game']} | price={r.get('price')} | edge={r.get('edgePct')} | score={r.get('baseballPredScore')} | telegram={r.get('telegramEligible')} | {r.get('mainReason')}")
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")
    lines += ["", f"JSON: {OUT_JSON}", "Rule: MONEYLINE ONLY. No O/U rows."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
