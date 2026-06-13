from pathlib import Path
import csv, json, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

INPUT = ROOT / ".astrodds" / "VVS-pitcher-context-latest.json"
OUT_JSON = ROOT / ".astrodds" / "VVS-bullpen-context-latest.json"
OUT_CSV = ROOT / ".astrodds" / "VVS-bullpen-context-latest.csv"
REPORT = BASE / "reports" / "10_bullpen_fatigue_snapshot_report.txt"

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fetch_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def nested(obj, keys, default=None):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def parse_dt(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def ip_float(value):
    if value in [None, ""]:
        return 0.0
    s = str(value)
    if "." not in s:
        try:
            return float(s)
        except Exception:
            return 0.0
    whole, frac = s.split(".", 1)
    try:
        whole = int(whole)
    except Exception:
        whole = 0
    outs = 1 if frac == "1" else 2 if frac == "2" else 0
    return whole + outs / 3

def feed(game_pk):
    return fetch_json(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")

def team_ids(game_feed):
    away = nested(game_feed, ["gameData", "teams", "away", "id"])
    home = nested(game_feed, ["gameData", "teams", "home", "id"])
    return away, home

def side_for_team(game_feed, team_id):
    away, home = team_ids(game_feed)
    if str(team_id) == str(away):
        return "away"
    if str(team_id) == str(home):
        return "home"
    return None

def is_final(game):
    status = game.get("status", {})
    return status.get("abstractGameState") == "Final" or status.get("detailedState") in ["Final", "Game Over", "Completed Early"]

def schedule_games(team_id, start_date, end_date):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
    data = fetch_json(url)
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if is_final(g):
                games.append({
                    "gamePk": g.get("gamePk"),
                    "officialDate": g.get("officialDate")
                })
    return games

def bullpen_ip_for_team(game_feed, team_id):
    side = side_for_team(game_feed, team_id)
    if not side:
        return {"bullpenIp": 0.0, "relievers": 0}

    players = nested(game_feed, ["liveData", "boxscore", "teams", side, "players"], {}) or {}
    bp_ip = 0.0
    relievers = 0

    for p in players.values():
        pitching = nested(p, ["stats", "pitching"], {})
        if not pitching:
            continue

        ip = ip_float(pitching.get("inningsPitched"))
        if ip <= 0:
            continue

        started = str(pitching.get("gamesStarted", "0")) == "1"
        if not started:
            bp_ip += ip
            relievers += 1

    return {"bullpenIp": round(bp_ip, 2), "relievers": relievers}

def bullpen_context(team_id, game_dt):
    if not team_id or not game_dt:
        return {"status": "missing"}

    start = (game_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    end = (game_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        games = schedule_games(team_id, start, end)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    ip1 = ip3 = ip7 = 0.0
    g1 = g3 = g7 = 0
    rel3 = 0
    details = []

    for g in games:
        try:
            official = datetime.fromisoformat(g["officialDate"] + "T00:00:00+00:00")
            days_back = (game_dt.date() - official.date()).days
            if days_back < 1 or days_back > 7:
                continue

            gf = feed(g["gamePk"])
            bp = bullpen_ip_for_team(gf, team_id)
            bp_ip = bp["bullpenIp"]

            if days_back <= 1:
                ip1 += bp_ip
                g1 += 1
            if days_back <= 3:
                ip3 += bp_ip
                g3 += 1
                rel3 += bp["relievers"]

            ip7 += bp_ip
            g7 += 1
            details.append(f"{g['officialDate']}: {bp_ip} BP IP")
        except Exception:
            continue

    score = 0
    flags = []

    if ip1 >= 4:
        score += 35
        flags.append("heavy_bullpen_yesterday")
    if ip3 >= 10:
        score += 35
        flags.append("heavy_bullpen_3d")
    elif ip3 >= 7:
        score += 20
        flags.append("moderate_bullpen_3d")
    if g3 >= 3:
        score += 15
        flags.append("three_games_in_three_days")
    if ip7 >= 22:
        score += 15
        flags.append("heavy_bullpen_7d")

    label = "high" if score >= 60 else "medium" if score >= 30 else "low"

    return {
        "status": "available",
        "games1d": g1,
        "games3d": g3,
        "games7d": g7,
        "ip1d": round(ip1, 2),
        "ip3d": round(ip3, 2),
        "ip7d": round(ip7, 2),
        "relievers3d": rel3,
        "score": score,
        "label": label,
        "flags": "|".join(flags) if flags else "none",
        "details": "; ".join(details)
    }

def add_ctx(row, prefix, ctx):
    row[f"{prefix}BullpenStatus"] = ctx.get("status")
    row[f"{prefix}BullpenGames1d"] = ctx.get("games1d")
    row[f"{prefix}BullpenGames3d"] = ctx.get("games3d")
    row[f"{prefix}BullpenGames7d"] = ctx.get("games7d")
    row[f"{prefix}BullpenIp1d"] = ctx.get("ip1d")
    row[f"{prefix}BullpenIp3d"] = ctx.get("ip3d")
    row[f"{prefix}BullpenIp7d"] = ctx.get("ip7d")
    row[f"{prefix}BullpenRelievers3d"] = ctx.get("relievers3d")
    row[f"{prefix}BullpenFatigueScore"] = ctx.get("score")
    row[f"{prefix}BullpenFatigueLabel"] = ctx.get("label")
    row[f"{prefix}BullpenFlags"] = ctx.get("flags")
    row[f"{prefix}BullpenDetails"] = ctx.get("details")
    row[f"{prefix}BullpenError"] = ctx.get("error")

def main():
    rows = read_json(INPUT)
    output = []
    cache = {}

    for row in rows:
        out = dict(row)
        game_pk = out.get("gamePk")
        game_dt = parse_dt(out.get("date"))

        if game_pk not in cache:
            cache[game_pk] = feed(game_pk)

        away_id, home_id = team_ids(cache[game_pk])
        out["awayTeamId"] = away_id
        out["homeTeamId"] = home_id

        away_ctx = bullpen_context(away_id, game_dt)
        home_ctx = bullpen_context(home_id, game_dt)

        add_ctx(out, "away", away_ctx)
        add_ctx(out, "home", home_ctx)

        flags = []
        if away_ctx.get("label") in ["medium", "high"]:
            flags.append(f"away_bullpen_{away_ctx.get('label')}_fatigue")
        if home_ctx.get("label") in ["medium", "high"]:
            flags.append(f"home_bullpen_{home_ctx.get('label')}_fatigue")

        out["bullpenContextFlags"] = "|".join(flags) if flags else "none"
        out["bullpenContextStatus"] = "ok"

        output.append(out)

    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    fields = sorted({k for r in output for k in r.keys()})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(output)

    lines = []
    lines.append("ASTRODDS 10 BULLPEN FATIGUE SNAPSHOT REPORT")
    lines.append("=" * 46)
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Output rows: {len(output)}")
    lines.append("")
    lines.append("Bullpen context:")

    for r in output:
        lines.append(
            f"- {r.get('game')} | Pick: {r.get('pick')} | "
            f"Away BP: {r.get('awayBullpenFatigueLabel')} {r.get('awayBullpenIp3d')} IP/3d | "
            f"Home BP: {r.get('homeBullpenFatigueLabel')} {r.get('homeBullpenIp3d')} IP/3d | "
            f"Flags: {r.get('bullpenContextFlags')}"
        )

    lines.append("")
    lines.append("Important: bullpen fatigue is informational only. It does not change VVS picks yet.")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"JSON: {OUT_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
