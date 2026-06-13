from pathlib import Path
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

LEDGER = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
REPORT = ROOT / "reports" / "23_repair_resolved_scores_report.txt"

def read_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def resolve_score(game_pk):
    data = fetch_json(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")

    teams = data.get("gameData", {}).get("teams", {})
    away_team = teams.get("away", {}).get("name", "")
    home_team = teams.get("home", {}).get("name", "")

    linescore = data.get("liveData", {}).get("linescore", {}).get("teams", {})
    away_runs = linescore.get("away", {}).get("runs")
    home_runs = linescore.get("home", {}).get("runs")

    if away_runs is None or home_runs is None:
        return None

    if int(away_runs) > int(home_runs):
        winner = away_team
    elif int(home_runs) > int(away_runs):
        winner = home_team
    else:
        winner = "push"

    return {
        "awayRuns": int(away_runs),
        "homeRuns": int(home_runs),
        "winner": winner
    }

def main():
    rows = read_json(LEDGER)
    repaired = 0
    errors = []

    for r in rows:
        if r.get("result") not in ["win", "loss", "push"]:
            continue

        if r.get("awayRuns") not in [None, ""] and r.get("homeRuns") not in [None, ""]:
            continue

        game_pk = r.get("gamePk")
        if not game_pk:
            continue

        try:
            score = resolve_score(game_pk)
        except Exception as e:
            errors.append(f"{r.get('game')}: {e}")
            continue

        if not score:
            continue

        r["awayRuns"] = score["awayRuns"]
        r["homeRuns"] = score["homeRuns"]
        r["winner"] = score["winner"]
        r["scoreRepairedAt"] = datetime.utcnow().isoformat() + "Z"
        repaired += 1

    LEDGER.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 23 REPAIR RESOLVED SCORES REPORT")
    lines.append("=" * 48)
    lines.append(f"Ledger rows: {len(rows)}")
    lines.append(f"Scores repaired: {repaired}")

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append(f"Updated ledger: {LEDGER}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
