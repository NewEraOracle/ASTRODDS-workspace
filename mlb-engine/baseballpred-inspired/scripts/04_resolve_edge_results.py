from pathlib import Path
import json
import urllib.request
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LEDGER = ROOT / ".astrodds" / "edge-tracking" / "edge-ledger.json"
REPORT = BASE / "reports" / "04_resolve_edge_results_report.txt"

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def fetch_game(game_id):
    if not game_id or not str(game_id).startswith("mlb-"):
        return None

    game_pk = str(game_id).replace("mlb-", "").strip()
    url = f"https://statsapi.mlb.com/api/v1/schedule?gamePk={game_pk}&hydrate=linescore,team"

    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    dates = data.get("dates", [])
    if not dates or not dates[0].get("games"):
        return None

    game = dates[0]["games"][0]

    status = game.get("status", {})
    abstract_state = status.get("abstractGameState", "")
    detailed_state = status.get("detailedState", "")

    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_team = away.get("team", {}).get("name", "")
    home_team = home.get("team", {}).get("name", "")

    away_score = away.get("score")
    home_score = home.get("score")

    is_final = abstract_state == "Final" or detailed_state in ["Final", "Game Over", "Completed Early"]

    winner = None
    if is_final and away_score is not None and home_score is not None:
        if away_score > home_score:
            winner = away_team
        elif home_score > away_score:
            winner = home_team

    return {
        "gamePk": game_pk,
        "isFinal": is_final,
        "status": detailed_state or abstract_state,
        "awayTeam": away_team,
        "homeTeam": home_team,
        "awayScore": away_score,
        "homeScore": home_score,
        "winner": winner,
    }

def main():
    rows = read_json(LEDGER)

    resolved_now = 0
    still_pending = 0
    errors = []

    for row in rows:
        if row.get("result") in ["win", "loss"]:
            continue

        try:
            game = fetch_game(row.get("gameId"))
        except Exception as e:
            errors.append(f"{row.get('gameId')}: {e}")
            still_pending += 1
            continue

        if not game:
            row["result"] = row.get("result", "pending")
            row["resolveNote"] = "Game not found from MLB StatsAPI."
            still_pending += 1
            continue

        row["mlbStatus"] = game["status"]
        row["awayScore"] = game["awayScore"]
        row["homeScore"] = game["homeScore"]

        if not game["isFinal"] or not game["winner"]:
            row["result"] = "pending"
            row["resolveNote"] = "Game not final yet."
            still_pending += 1
            continue

        row["winner"] = game["winner"]
        row["resolvedAt"] = datetime.utcnow().isoformat() + "Z"

        if row.get("pick") == game["winner"]:
            row["result"] = "win"
        else:
            row["result"] = "loss"

        resolved_now += 1

    write_json(LEDGER, rows)

    bucket_stats = defaultdict(lambda: {"total": 0, "win": 0, "loss": 0, "pending": 0})

    for row in rows:
        bucket = row.get("edgeBucket", "unknown")
        result = row.get("result", "pending")
        bucket_stats[bucket]["total"] += 1
        bucket_stats[bucket][result] = bucket_stats[bucket].get(result, 0) + 1

    lines = []
    lines.append("ASTRODDS 04 RESOLVE EDGE RESULTS REPORT")
    lines.append("=" * 44)
    lines.append(f"Ledger rows: {len(rows)}")
    lines.append(f"Resolved this run: {resolved_now}")
    lines.append(f"Still pending: {still_pending}")
    lines.append("")
    lines.append("Bucket performance:")

    for bucket in sorted(bucket_stats.keys()):
        s = bucket_stats[bucket]
        resolved = s.get("win", 0) + s.get("loss", 0)
        win_rate = round((s.get("win", 0) / resolved) * 100, 2) if resolved else None
        lines.append(
            f"{bucket}: total={s['total']} win={s.get('win', 0)} loss={s.get('loss', 0)} "
            f"pending={s.get('pending', 0)} winRate={win_rate}"
        )

    lines.append("")
    lines.append("Ledger:")
    for row in rows:
        lines.append(
            f"- {row.get('date')} | {row.get('awayTeam')} @ {row.get('homeTeam')} | "
            f"Pick: {row.get('pick')} | Result: {row.get('result')} | "
            f"Winner: {row.get('winner', '-')}"
        )

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")
    print(f"Updated ledger: {LEDGER}")

if __name__ == "__main__":
    main()
