from pathlib import Path
from datetime import datetime, timezone
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_BOARD = ASTRO / "ASTRODDS-full-slate-game-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-full-slate-game-board-moneyline-expanded-latest.json"
REPORT = REPORTS / "202_expand_moneyline_full_slate_board_report.txt"

FULL_SLATE_CSVS = [
    ASTRO / "ASTRODDS-full-slate-context-final-latest.csv",
    ASTRO / "ASTRODDS-full-slate-context-input-latest.csv",
    ASTRO / "ASTRODDS-engine-final-signals-latest.csv",
]

ALIASES = {
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
    return ALIASES.get(norm(raw), raw)

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

def fnum(v, default=None):
    try:
        s = str(v).strip().replace("%", "").replace("+", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def first(row, keys, default=""):
    for k in keys:
        if isinstance(row, dict) and k in row and str(row.get(k, "")).strip() != "":
            return row.get(k)
    return default

def add_game(games, game="", away="", home="", source=""):
    if not away or not home:
        pa, ph = parse_game(game)
        away = away or pa
        home = home or ph
    if not game and away and home:
        game = f"{away} @ {home}"
    key = game_key(game, away, home)
    if not key:
        return
    if key not in games:
        games[key] = {"game": game, "awayTeam": away, "homeTeam": home, "sources": set()}
    if source:
        games[key]["sources"].add(source)

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    board = load_json(IN_BOARD)
    rows = board.get("gameBoard", []) if isinstance(board, dict) else []

    games = {}
    existing_ml_keys = set()

    for r in rows:
        game = r.get("game", "")
        away = r.get("awayTeam", "")
        home = r.get("homeTeam", "")
        add_game(games, game, away, home, "existing game board")
        if r.get("marketType") == "MONEYLINE":
            existing_ml_keys.add((game_key(game, away, home), norm(r.get("pick", ""))))

    # Add every game visible in slate/context CSVs, not only existing picks.
    for src in FULL_SLATE_CSVS:
        for r in read_csv(src):
            game = first(r, ["game", "Game", "matchup"])
            away = first(r, ["awayTeam", "away_team", "away"])
            home = first(r, ["homeTeam", "home_team", "home"])
            add_game(games, game, away, home, src.name)

    added = []
    expanded = list(rows)

    for key, g in games.items():
        away = g.get("awayTeam", "")
        home = g.get("homeTeam", "")
        game = g.get("game", "") or f"{away} @ {home}"

        # Make sure BOTH teams appear on moneyline board if no row exists.
        for team, side in [(away, "away"), (home, "home")]:
            if not team:
                continue
            ml_key = (key, norm(team))
            if ml_key in existing_ml_keys:
                continue
            newrow = {
                "rank": None,
                "game": game,
                "awayTeam": away,
                "homeTeam": home,
                "pick": team,
                "marketType": "MONEYLINE",
                "line": "",
                "price": "",
                "modelProbability": "",
                "edgePct": "",
                "edgeRuns": "",
                "baseballPredScore": 0,
                "grade": "NO_BET",
                "status": "NO_BET",
                "telegramEligible": False,
                "mainReason": "Game scanned, but no clean Moneyline edge from current live/BaseballPred files.",
                "riskReason": "No official price/edge/grade strong enough to promote this side.",
                "contextFlags": [],
                "contexts": {},
                "sourceFilesUsed": list(g.get("sources", [])),
                "side": side,
            }
            expanded.append(newrow)
            added.append(newrow)
            existing_ml_keys.add(ml_key)

    status_order = {"OFFICIAL":0, "A_PAPER":1, "REVIEW":2, "WATCH":3, "BLOCKED":4, "NO_BET":5}
    expanded.sort(key=lambda r: (status_order.get(r.get("status", "NO_BET"), 9), -(fnum(r.get("baseballPredScore"), 0) or 0)))
    for i, r in enumerate(expanded, 1):
        r["rank"] = i

    counts = {}
    for r in expanded:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalGames": len(games),
        "rowsBefore": len(rows),
        "rowsAfter": len(expanded),
        "moneylineRowsAdded": len(added),
        "counts": counts,
        "gameBoard": expanded,
        "rule": "Dashboard only. Adds NO_BET moneyline rows for all scanned games.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 202 EXPAND MONEYLINE FULL SLATE BOARD",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Games found: {out['totalGames']}",
        f"Rows before: {out['rowsBefore']}",
        f"Rows after: {out['rowsAfter']}",
        f"Moneyline rows added: {out['moneylineRowsAdded']}",
        "",
        "Added Moneyline NO_BET rows:",
    ]
    for r in added[:40]:
        lines.append(f"- {r['pick']} | {r['game']} | {r['mainReason']}")
    lines += ["", f"JSON: {OUT_JSON}", "Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
