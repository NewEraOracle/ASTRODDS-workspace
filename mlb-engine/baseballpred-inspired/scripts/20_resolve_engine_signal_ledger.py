from pathlib import Path
import csv
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

LEDGER_JSON = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
LEDGER_CSV = WORKSPACE / ".astrodds" / "ASTRODDS-engine-signal-ledger.csv"
REPORT = ROOT / "reports" / "20_resolve_engine_signal_ledger_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def fetch_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(x):
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def is_final(status):
    abstract = status.get("abstractGameState", "")
    detailed = status.get("detailedState", "")
    return abstract == "Final" or detailed in ["Final", "Game Over", "Completed Early"]

def resolve_game(game_pk):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    data = fetch_json(url)

    status = data.get("gameData", {}).get("status", {})
    detailed = status.get("detailedState", "")
    abstract = status.get("abstractGameState", "")

    if not is_final(status):
        return {
            "resolved": False,
            "status": detailed or abstract or "not_final",
        }

    teams = data.get("gameData", {}).get("teams", {})
    away_team = teams.get("away", {}).get("name", "")
    home_team = teams.get("home", {}).get("name", "")

    linescore = data.get("liveData", {}).get("linescore", {}).get("teams", {})
    away_runs = linescore.get("away", {}).get("runs")
    home_runs = linescore.get("home", {}).get("runs")

    if away_runs is None or home_runs is None:
        return {
            "resolved": False,
            "status": "final_but_score_missing",
        }

    if int(away_runs) > int(home_runs):
        winner = away_team
    elif int(home_runs) > int(away_runs):
        winner = home_team
    else:
        winner = "push"

    return {
        "resolved": True,
        "status": detailed,
        "awayTeam": away_team,
        "homeTeam": home_team,
        "awayRuns": int(away_runs),
        "homeRuns": int(home_runs),
        "winner": winner,
    }

def edge_bucket(edge):
    e = fnum(edge)
    if e is None:
        return "missing"
    if e < 3:
        return "0-3%"
    if e < 5:
        return "3-5%"
    if e < 8:
        return "5-8%"
    if e < 12:
        return "8-12%"
    return "12%+"

def paper_roi(row):
    market = fnum(row.get("marketProbability"))
    result = row.get("result")

    if market is None or market <= 0:
        return 0.0

    decimal_odds = 1 / market

    if result == "win":
        return decimal_odds - 1

    if result == "loss":
        return -1.0

    return 0.0

def summarize(rows, group_key):
    groups = {}

    for r in rows:
        key = r.get(group_key, "unknown") or "unknown"

        if key not in groups:
            groups[key] = {
                "total": 0,
                "resolved": 0,
                "win": 0,
                "loss": 0,
                "pending": 0,
                "paperProfitUnits": 0.0,
            }

        g = groups[key]
        g["total"] += 1

        result = r.get("result", "pending")

        if result == "win":
            g["resolved"] += 1
            g["win"] += 1
            g["paperProfitUnits"] += paper_roi(r)
        elif result == "loss":
            g["resolved"] += 1
            g["loss"] += 1
            g["paperProfitUnits"] += paper_roi(r)
        else:
            g["pending"] += 1

    for g in groups.values():
        resolved = g["resolved"]
        g["winRate"] = round((g["win"] / resolved) * 100, 2) if resolved else None
        g["paperProfitUnits"] = round(g["paperProfitUnits"], 3)
        g["paperROI"] = round((g["paperProfitUnits"] / resolved) * 100, 2) if resolved else None

    return groups

def main():
    ledger = read_json(LEDGER_JSON, [])

    if not isinstance(ledger, list):
        ledger = []

    resolved_this_run = 0
    still_pending = 0
    errors = []

    for row in ledger:
        if row.get("result") in ["win", "loss", "push", "void"]:
            continue

        game_pk = row.get("gamePk")

        if not game_pk:
            row["resolveError"] = "missing_gamePk"
            still_pending += 1
            continue

        try:
            result = resolve_game(game_pk)
        except Exception as e:
            row["resolveError"] = str(e)
            errors.append(f"{row.get('game')}: {e}")
            still_pending += 1
            continue

        row["mlbResolveStatus"] = result.get("status")

        if not result.get("resolved"):
            row["result"] = "pending"
            still_pending += 1
            continue

        winner = result.get("winner")
        row["winner"] = winner
        row["awayRuns"] = result.get("awayRuns")
        row["homeRuns"] = result.get("homeRuns")
        row["resolvedAt"] = datetime.utcnow().isoformat() + "Z"

        if winner == "push":
            row["result"] = "push"
        elif row.get("pick") == winner:
            row["result"] = "win"
        else:
            row["result"] = "loss"

        resolved_this_run += 1

    for row in ledger:
        row["calibratedEdgeBucket"] = edge_bucket(row.get("calibratedEdgePct"))
        row["paperProfitUnits"] = round(paper_roi(row), 3)

    write_json(LEDGER_JSON, ledger)

    fields = sorted({k for row in ledger for k in row.keys()})
    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(ledger)

    by_decision = summarize(ledger, "finalEngineDecision")
    by_grade = summarize(ledger, "finalGrade")
    by_edge = summarize(ledger, "calibratedEdgeBucket")

    lines = []
    lines.append("ASTRODDS 20 RESOLVE ENGINE SIGNAL LEDGER REPORT")
    lines.append("=" * 52)
    lines.append("")
    lines.append(f"Ledger rows: {len(ledger)}")
    lines.append(f"Resolved this run: {resolved_this_run}")
    lines.append(f"Still pending: {still_pending}")
    lines.append("")

    lines.append("Performance by final decision:")
    for k, g in sorted(by_decision.items()):
        lines.append(
            f"- {k}: total={g['total']} resolved={g['resolved']} "
            f"win={g['win']} loss={g['loss']} pending={g['pending']} "
            f"winRate={g['winRate']} paperROI={g['paperROI']}% profit={g['paperProfitUnits']}u"
        )

    lines.append("")
    lines.append("Performance by grade:")
    for k, g in sorted(by_grade.items()):
        lines.append(
            f"- {k}: total={g['total']} resolved={g['resolved']} "
            f"win={g['win']} loss={g['loss']} pending={g['pending']} "
            f"winRate={g['winRate']} paperROI={g['paperROI']}% profit={g['paperProfitUnits']}u"
        )

    lines.append("")
    lines.append("Performance by calibrated edge bucket:")
    for k, g in sorted(by_edge.items()):
        lines.append(
            f"- {k}: total={g['total']} resolved={g['resolved']} "
            f"win={g['win']} loss={g['loss']} pending={g['pending']} "
            f"winRate={g['winRate']} paperROI={g['paperROI']}% profit={g['paperProfitUnits']}u"
        )

    lines.append("")
    lines.append("Ledger:")
    for r in ledger:
        lines.append(
            f"- {r.get('date')} | {r.get('game')} | Pick: {r.get('pick')} | "
            f"Decision: {r.get('finalEngineDecision')} | Grade: {r.get('finalGrade')} | "
            f"Result: {r.get('result')} | Winner: {r.get('winner', '')} | "
            f"Score: {r.get('awayRuns', '-')}-{r.get('homeRuns', '-')}"
        )

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append(f"Updated JSON: {LEDGER_JSON}")
    lines.append(f"Updated CSV: {LEDGER_CSV}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
