# -*- coding: utf-8 -*-
from pathlib import Path
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-alert-ledger.json"
RESULT_LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-results-ledger.json"
REPORT = BASE / "reports" / "81_telegram_result_tracking_report.txt"

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_game(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def game_result(entry):
    game_pk = entry.get("gamePk")

    if not game_pk:
        return None, "missing_gamePk"

    try:
        data = fetch_game(game_pk)
    except Exception as e:
        return None, f"fetch_error:{e}"

    status = str(data.get("gameData", {}).get("status", {}).get("abstractGameState") or "")
    detailed = str(data.get("gameData", {}).get("status", {}).get("detailedState") or "")

    if status.lower() != "final" and detailed.lower() != "final":
        return None, "not_final"

    teams = data.get("gameData", {}).get("teams", {})
    home_name = teams.get("home", {}).get("name")
    away_name = teams.get("away", {}).get("name")

    linescore = data.get("liveData", {}).get("linescore", {})
    home_runs = linescore.get("teams", {}).get("home", {}).get("runs")
    away_runs = linescore.get("teams", {}).get("away", {}).get("runs")

    if home_runs is None or away_runs is None:
        return None, "missing_score"

    winner = home_name if home_runs > away_runs else away_name if away_runs > home_runs else "PUSH"
    pick = entry.get("pick")

    if winner == "PUSH":
        result = "PUSH"
    elif pick and winner and str(pick).lower() == str(winner).lower():
        result = "WIN"
    else:
        result = "LOSS"

    return {
        "gamePk": game_pk,
        "game": entry.get("game"),
        "pick": pick,
        "winner": winner,
        "homeTeam": home_name,
        "awayTeam": away_name,
        "homeRuns": home_runs,
        "awayRuns": away_runs,
        "result": result,
        "publicCategory": entry.get("publicCategory"),
        "marketProbability": entry.get("marketProbability"),
        "stake": 0.05 if entry.get("publicCategory") == "A_PICK" else 0.02,
        "settledAt": datetime.utcnow().isoformat() + "Z",
    }, None

def roi_units(result_row):
    if not result_row:
        return 0.0

    result = result_row.get("result")
    stake = float(result_row.get("stake") or 0)
    p = result_row.get("marketProbability")

    try:
        p = float(p)
    except Exception:
        p = None

    if result == "PUSH":
        return 0.0

    if result == "LOSS":
        return -stake

    if result == "WIN":
        if p and 0 < p < 1:
            return stake * ((1 / p) - 1)
        return stake

    return 0.0

def main():
    telegram_ledger = read_json(LEDGER, [])
    result_ledger = read_json(RESULT_LEDGER, [])

    settled_keys = set(x.get("alertKey") for x in result_ledger)
    candidates = [
        x for x in telegram_ledger
        if x.get("publicCategory") in ["A_PICK", "VALUE_LEAN"]
        and x.get("alertKey") not in settled_keys
    ]

    new_results = []
    skipped = []

    for entry in candidates:
        result, reason = game_result(entry)
        if result:
            result["alertKey"] = entry.get("alertKey")
            result["roiUnits"] = round(roi_units(result), 4)
            new_results.append(result)
        else:
            skipped.append({
                "alertKey": entry.get("alertKey"),
                "game": entry.get("game"),
                "pick": entry.get("pick"),
                "reason": reason,
            })

    if new_results:
        result_ledger.extend(new_results)
        write_json(RESULT_LEDGER, result_ledger)

    a_results = [x for x in result_ledger if x.get("publicCategory") == "A_PICK"]
    v_results = [x for x in result_ledger if x.get("publicCategory") == "VALUE_LEAN"]

    def record(rows):
        wins = sum(1 for x in rows if x.get("result") == "WIN")
        losses = sum(1 for x in rows if x.get("result") == "LOSS")
        pushes = sum(1 for x in rows if x.get("result") == "PUSH")
        roi = round(sum(float(x.get("roiUnits") or 0) for x in rows), 4)
        return wins, losses, pushes, roi

    aw, al, ap, aroi = record(a_results)
    vw, vl, vp, vroi = record(v_results)

    lines = [
        "ASTRODDS 81 TELEGRAM RESULT TRACKING REPORT",
        "=" * 56,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        f"Telegram ledger rows: {len(telegram_ledger)}",
        f"Candidates checked: {len(candidates)}",
        f"New settled results: {len(new_results)}",
        f"Skipped/unsettled: {len(skipped)}",
        "",
        f"A PICK record: {aw}-{al}-{ap} | ROI units: {aroi}",
        f"VALUE LEAN record: {vw}-{vl}-{vp} | ROI units: {vroi}",
        "",
        "New results:",
    ]

    for row in new_results:
        lines.append(f"- {row.get('publicCategory')} | {row.get('game')} | Pick: {row.get('pick')} | Winner: {row.get('winner')} | Result: {row.get('result')} | ROI: {row.get('roiUnits')}")

    if not new_results:
        lines.append("- none")

    lines.extend([
        "",
        "Skipped/unsettled:",
    ])

    for row in skipped[:20]:
        lines.append(f"- {row.get('game')} | Pick: {row.get('pick')} | Reason: {row.get('reason')}")

    if not skipped:
        lines.append("- none")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
