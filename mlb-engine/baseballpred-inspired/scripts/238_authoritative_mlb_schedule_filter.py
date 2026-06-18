from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-authoritative-schedule-filter-latest.json"
REPORT = REPORTS / "238_authoritative_mlb_schedule_filter_report.txt"

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
    "white sox": "Chicago White Sox",
    "red sox": "Boston Red Sox",
    "blue jays": "Toronto Blue Jays",
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

def key_pair(away, home):
    return f"{norm(canon(away))}@{norm(canon(home))}"

def game_key_from_row(row):
    away = row.get("awayTeam") or ""
    home = row.get("homeTeam") or ""
    if away and home:
        return key_pair(away, home)
    a, h = parse_game(row.get("game", ""))
    return key_pair(a, h) if a and h else norm(row.get("game", ""))

def fetch_schedule():
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    games = {}
    for d in data.get("dates", []):
        for g in d.get("games", []):
            teams = g.get("teams", {})
            away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
            home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
            if not away or not home:
                continue
            status = (g.get("status") or {}).get("detailedState", "") or (g.get("status") or {}).get("abstractGameState", "")
            abstract = (g.get("status") or {}).get("abstractGameState", "")
            game_date = g.get("gameDate", "")
            k = key_pair(away, home)
            games[k] = {
                "awayTeam": away,
                "homeTeam": home,
                "officialGame": f"{away} @ {home}",
                "liveMlbStatus": status,
                "abstractStatus": abstract,
                "gameDate": game_date,
                "gamePk": g.get("gamePk", ""),
            }
    return today, games

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    schedule_date, official = fetch_schedule()
    data = load_json(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    kept = []
    rejected = []
    seen_keys = set()

    for r in rows:
        r = dict(r)
        k = game_key_from_row(r)
        if k in official:
            info = official[k]
            seen_keys.add(k)
            r["game"] = info["officialGame"]
            r["awayTeam"] = info["awayTeam"]
            r["homeTeam"] = info["homeTeam"]
            r["liveMlbStatus"] = info["liveMlbStatus"]
            r["mlbStatus"] = info["liveMlbStatus"]
            r["liveGameDate"] = info["gameDate"]
            r["liveGamePk"] = info["gamePk"]
            r["scheduleSourceUsed"] = "MLB StatsAPI authoritative schedule"
            kept.append(r)
        else:
            r["rejectedReason"] = "Game is not on authoritative MLB schedule for today."
            r["originalGame"] = r.get("game", "")
            rejected.append(r)

    missing_games = []
    for k, info in official.items():
        if k not in seen_keys:
            missing_games.append(info)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scheduleDateET": schedule_date,
        "officialGames": len(official),
        "inputRows": len(rows),
        "keptRows": len(kept),
        "rejectedRows": len(rejected),
        "officialGamesMissingFromPriceBoard": len(missing_games),
        "keptMoneylineBoard": kept,
        "rejectedRowsPreview": rejected[:80],
        "missingOfficialGames": missing_games,
        "rule": "Moneyline board must match authoritative MLB schedule for today. Non-schedule games are rejected before model/edge.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({
        "generatedAt": out["generatedAt"],
        "moneylineRows": len(kept),
        "moneylineBoard": kept,
        "rejectedRows": len(rejected),
        "missingOfficialGames": missing_games,
        "rule": out["rule"],
    }, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 238 AUTHORITATIVE MLB SCHEDULE FILTER",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        f"Schedule date ET: {schedule_date}",
        "",
        f"Official MLB games today: {out['officialGames']}",
        f"Input moneyline rows: {out['inputRows']}",
        f"Kept rows: {out['keptRows']}",
        f"Rejected stale/nonexistent rows: {out['rejectedRows']}",
        f"Official games missing from price board: {out['officialGamesMissingFromPriceBoard']}",
        "",
        "OFFICIAL GAMES TODAY:",
    ]
    for info in official.values():
        lines.append(f"- {info['officialGame']} | status={info['liveMlbStatus']} | gamePk={info['gamePk']}")

    lines += ["", "REJECTED STALE/NONEXISTENT ROWS:"]
    if rejected:
        for r in rejected[:60]:
            lines.append(f"- {r.get('pick')} | {r.get('originalGame')} | price={r.get('price')} | reason={r.get('rejectedReason')}")
    else:
        lines.append("- none")

    lines += ["", "OFFICIAL GAMES MISSING FROM PRICE BOARD:"]
    if missing_games:
        for info in missing_games:
            lines.append(f"- {info['officialGame']} | status={info['liveMlbStatus']} | gamePk={info['gamePk']}")
    else:
        lines.append("- none")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: schedule source of truth is MLB StatsAPI today."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
