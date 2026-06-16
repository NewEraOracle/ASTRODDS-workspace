from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import json
import urllib.parse
import urllib.request
import time

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_CSV = ASTRO / "ASTRODDS-bpen-whip35-exact-statsapi-latest.csv"
OUT_JSON = ASTRO / "ASTRODDS-bpen-whip35-exact-statsapi-latest.json"
GAME_CSV = ASTRO / "ASTRODDS-bpen-game-relief-stats-latest.csv"
REPORT = REPORTS / "183_build_exact_bpen_whip35_from_statsapi_report.txt"

ET = ZoneInfo("America/New_York")

FIELDS_GAME = [
    "date", "gamePk", "teamId", "teamName", "opponent", "isHome",
    "relief_ip", "relief_hits", "relief_walks", "relief_pitchers", "status"
]

FIELDS_TEAM = [
    "as_of_date", "teamId", "teamName", "games_in_window",
    "bpen_ip_35", "bpen_hits_35", "bpen_walks_35", "Bpen_WHIP_35",
    "source", "window_days"
]

def fetch_json(url, params=None, timeout=25):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ASTRODDS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def ip_to_float(ip):
    s = str(ip or "0").strip()
    if not s:
        return 0.0
    if "." not in s:
        try:
            return float(s)
        except Exception:
            return 0.0
    whole, frac = s.split(".", 1)
    try:
        whole_i = int(whole)
    except Exception:
        whole_i = 0
    outs = 0
    if frac.startswith("1"):
        outs = 1
    elif frac.startswith("2"):
        outs = 2
    return whole_i + outs / 3.0

def fnum(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

def is_final(game):
    status = game.get("status", {})
    abstract = str(status.get("abstractGameState", "")).lower()
    detailed = str(status.get("detailedState", "")).lower()
    coded = str(status.get("codedGameState", "")).upper()
    return abstract == "final" or "final" in detailed or coded in ("F", "FT", "FR")

def get_schedule(start_date, end_date):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "startDate": start_date,
        "endDate": end_date,
    }
    data = fetch_json(url, params)
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if is_final(g):
                games.append(g)
    return games

def get_boxscore(game_pk):
    return fetch_json(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore")

def pitcher_relief_stats(team_box):
    # MLB boxscore has pitching player IDs in team_box["pitchers"].
    # Each player stats.pitching usually contains game-level gamesStarted.
    relief = {"ip": 0.0, "hits": 0.0, "walks": 0.0, "pitchers": 0}
    players = team_box.get("players", {})
    pitcher_ids = team_box.get("pitchers", [])

    for pid in pitcher_ids:
        pkey = f"ID{pid}" if not str(pid).startswith("ID") else str(pid)
        player = players.get(pkey, {})
        pitching = player.get("stats", {}).get("pitching", {})
        if not pitching:
            continue

        gs = fnum(pitching.get("gamesStarted", 0))
        # Starter = gamesStarted == 1 for that game. Relievers = 0.
        if gs >= 1:
            continue

        ip = ip_to_float(pitching.get("inningsPitched", "0"))
        if ip <= 0:
            continue

        relief["ip"] += ip
        relief["hits"] += fnum(pitching.get("hits", 0))
        relief["walks"] += fnum(pitching.get("baseOnBalls", 0))
        relief["pitchers"] += 1

    return relief

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    days = 35
    today = datetime.now(ET).date()
    start = today - timedelta(days=days)
    start_s = start.isoformat()
    end_s = today.isoformat()

    games = get_schedule(start_s, end_s)
    game_rows = []
    team_roll = {}

    errors = []

    for idx, game in enumerate(games, 1):
        game_pk = game.get("gamePk")
        game_date = str(game.get("gameDate", ""))[:10]
        teams = game.get("teams", {})
        home_name = teams.get("home", {}).get("team", {}).get("name", "")
        away_name = teams.get("away", {}).get("team", {}).get("name", "")

        try:
            box = get_boxscore(game_pk)
            time.sleep(0.05)
        except Exception as exc:
            errors.append(f"{game_pk}: {exc}")
            continue

        for side in ["home", "away"]:
            team_box = box.get("teams", {}).get(side, {})
            team_info = team_box.get("team", {})
            team_id = str(team_info.get("id", ""))
            team_name = team_info.get("name", "")
            opponent = away_name if side == "home" else home_name

            relief = pitcher_relief_stats(team_box)

            row = {
                "date": game_date,
                "gamePk": game_pk,
                "teamId": team_id,
                "teamName": team_name,
                "opponent": opponent,
                "isHome": "true" if side == "home" else "false",
                "relief_ip": round(relief["ip"], 4),
                "relief_hits": int(relief["hits"]),
                "relief_walks": int(relief["walks"]),
                "relief_pitchers": relief["pitchers"],
                "status": game.get("status", {}).get("detailedState", ""),
            }
            game_rows.append(row)

            agg = team_roll.setdefault(team_id, {
                "teamId": team_id,
                "teamName": team_name,
                "games": 0,
                "ip": 0.0,
                "hits": 0.0,
                "walks": 0.0,
            })
            if relief["ip"] > 0:
                agg["games"] += 1
                agg["ip"] += relief["ip"]
                agg["hits"] += relief["hits"]
                agg["walks"] += relief["walks"]

    team_rows = []
    for team_id, agg in sorted(team_roll.items(), key=lambda kv: kv[1]["teamName"]):
        ip = agg["ip"]
        whip = ((agg["hits"] + agg["walks"]) / ip) if ip > 0 else ""
        team_rows.append({
            "as_of_date": today.isoformat(),
            "teamId": team_id,
            "teamName": agg["teamName"],
            "games_in_window": agg["games"],
            "bpen_ip_35": round(ip, 4),
            "bpen_hits_35": int(agg["hits"]),
            "bpen_walks_35": int(agg["walks"]),
            "Bpen_WHIP_35": "" if whip == "" else round(whip, 4),
            "source": "mlb_statsapi_boxscores_relief_pitchers",
            "window_days": days,
        })

    write_csv(GAME_CSV, game_rows, FIELDS_GAME)
    write_csv(OUT_CSV, team_rows, FIELDS_TEAM)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "window": {"start": start_s, "end": end_s, "days": days},
        "gamesFinalParsed": len(games),
        "gameReliefRows": len(game_rows),
        "teamRows": len(team_rows),
        "errors": errors[:20],
        "csv": str(OUT_CSV),
        "gameCsv": str(GAME_CSV),
        "definition": "Bpen_WHIP_35 = (reliever hits + reliever walks) / reliever innings pitched across final MLB games in last 35 calendar days.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 183 EXACT BPEN WHIP35 FROM MLB STATSAPI",
        "=" * 74,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Formula:",
        "Bpen_WHIP_35 = (H_35 + BB_35) / IP_35",
        "",
        f"Window: {start_s} to {end_s}",
        f"Final games parsed: {len(games)}",
        f"Game relief rows: {len(game_rows)}",
        f"Team rows: {len(team_rows)}",
        f"Errors: {len(errors)}",
        "",
        "Top team rows:",
    ]
    for r in team_rows[:30]:
        lines.append(
            f"- {r['teamName']} | Games={r['games_in_window']} | IP={r['bpen_ip_35']} | "
            f"H={r['bpen_hits_35']} | BB={r['bpen_walks_35']} | Bpen_WHIP_35={r['Bpen_WHIP_35']}"
        )

    lines += [
        "",
        f"CSV: {OUT_CSV}",
        f"Game CSV: {GAME_CSV}",
        f"JSON: {OUT_JSON}",
        "",
        "Rule:",
        "- This uses MLB StatsAPI boxscore relief pitching, not Odds API credits.",
        "- It does not replace live picks automatically.",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
