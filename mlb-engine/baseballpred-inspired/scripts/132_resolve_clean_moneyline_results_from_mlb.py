from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import re
import sys

try:
    import requests
except Exception as exc:
    print("ERROR: requests package missing:", exc)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

CLEAN_CSV = ASTRO / "ASTRODDS-clean-moneyline-record.csv"
REPORT = REPORTS / "132_resolve_clean_moneyline_results_from_mlb_report.txt"

ET = ZoneInfo("America/New_York")

TEAM_ALIASES = {
    "athletics": "athletics",
    "oakland athletics": "athletics",
    "a's": "athletics",
    "tampa bay rays": "tampa bay rays",
    "los angeles dodgers": "los angeles dodgers",
    "kansas city royals": "kansas city royals",
    "washington nationals": "washington nationals",
    "los angeles angels": "los angeles angels",
    "la angels": "los angeles angels",
    "arizona diamondbacks": "arizona diamondbacks",
    "diamondbacks": "arizona diamondbacks",
    "pittsburgh pirates": "pittsburgh pirates",
    "houston astros": "houston astros",
}

def now_et():
    return datetime.now(ET).isoformat()

def norm_team(value):
    s = str(value or "").lower().strip()
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)
    return TEAM_ALIASES.get(s, s)

def parse_game_teams(game):
    g = str(game or "")
    if " @ " in g:
        a, h = g.split(" @ ", 1)
        return norm_team(a), norm_team(h)
    if " vs. " in g:
        a, h = g.split(" vs. ", 1)
        return norm_team(a), norm_team(h)
    if " vs " in g:
        a, h = g.split(" vs ", 1)
        return norm_team(a), norm_team(h)
    return "", ""

def read_rows():
    if not CLEAN_CSV.exists():
        raise FileNotFoundError(f"Missing CSV: {CLEAN_CSV}")
    with CLEAN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_rows(rows):
    if not rows:
        return

    base_fields = [
        "date", "game", "pick", "result", "model", "edge", "stake",
        "status", "final_score", "resolved_at", "notes"
    ]

    existing = []
    for r in rows:
        for k in r.keys():
            if k not in existing:
                existing.append(k)

    fields = []
    for k in base_fields:
        if k not in fields:
            fields.append(k)
    for k in existing:
        if k not in fields:
            fields.append(k)

    backup = CLEAN_CSV.with_suffix(".before-132-resolve.csv")
    CLEAN_CSV.replace(backup)

    with CLEAN_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            clean = {k: r.get(k, "") for k in fields}
            w.writerow(clean)

def mlb_schedule(date_str):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": date_str,
        "hydrate": "linescore"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    games = []
    for d in data.get("dates", []):
        games.extend(d.get("games", []))
    return games

def is_final(game_obj):
    status = game_obj.get("status", {})
    abstract_state = str(status.get("abstractGameState", "")).lower()
    detailed_state = str(status.get("detailedState", "")).lower()
    status_code = str(status.get("codedGameState", "")).upper()
    return (
        abstract_state == "final"
        or "final" in detailed_state
        or status_code in ("F", "FT", "FR")
    )

def find_matching_game(row, schedule_games):
    row_away, row_home = parse_game_teams(row.get("game"))
    pick = norm_team(row.get("pick"))

    best = None
    for g in schedule_games:
        teams = g.get("teams", {})
        away_name = norm_team(teams.get("away", {}).get("team", {}).get("name", ""))
        home_name = norm_team(teams.get("home", {}).get("team", {}).get("name", ""))

        exact = row_away and row_home and away_name == row_away and home_name == row_home
        loose = pick in (away_name, home_name) and (
            row_away in (away_name, home_name) or row_home in (away_name, home_name)
        )

        if exact or loose:
            best = g
            break

    return best

def resolve_row(row, game_obj):
    teams = game_obj.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_team = norm_team(away.get("team", {}).get("name", ""))
    home_team = norm_team(home.get("team", {}).get("name", ""))

    away_score = away.get("score")
    home_score = home.get("score")

    if away_score is None or home_score is None:
        return False, "missing score"

    try:
        away_score = int(away_score)
        home_score = int(home_score)
    except Exception:
        return False, "bad score"

    if not is_final(game_obj):
        row["result"] = "pending"
        row["final_score"] = f"{away_score}-{home_score}"
        row["resolved_at"] = ""
        return False, "not final"

    if away_score > home_score:
        winner = away_team
    elif home_score > away_score:
        winner = home_team
    else:
        row["result"] = "push"
        row["final_score"] = f"{away_score}-{home_score}"
        row["resolved_at"] = now_et()
        return True, "tie/push"

    pick = norm_team(row.get("pick"))

    row["result"] = "win" if pick == winner else "loss"
    row["final_score"] = f"{away_score}-{home_score}"
    row["resolved_at"] = now_et()
    return True, f"winner={winner}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    rows = read_rows()

    pending_rows = [
        r for r in rows
        if str(r.get("status", "")).strip() == "clean_apick"
        and str(r.get("result", "")).strip().lower() in ("pending", "", "tbd")
    ]

    lines = [
        "ASTRODDS 132 RESOLVE CLEAN MONEYLINE RESULTS FROM MLB",
        "=" * 70,
        f"Generated ET: {now_et()}",
        f"CSV: {CLEAN_CSV}",
        f"Rows total: {len(rows)}",
        f"Pending clean rows: {len(pending_rows)}",
        ""
    ]

    if not pending_rows:
        lines.append("No pending rows to resolve.")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    schedules = {}
    resolved = 0
    still_pending = 0
    not_found = 0

    for row in pending_rows:
        date_str = str(row.get("date", "")).strip()
        game_name = row.get("game", "")
        pick = row.get("pick", "")

        if not date_str:
            lines.append(f"SKIP missing date | {game_name} | {pick}")
            continue

        if date_str not in schedules:
            try:
                schedules[date_str] = mlb_schedule(date_str)
            except Exception as exc:
                lines.append(f"ERROR schedule fetch failed for {date_str}: {exc}")
                schedules[date_str] = []

        match = find_matching_game(row, schedules[date_str])

        if not match:
            not_found += 1
            lines.append(f"NOT FOUND | {date_str} | {game_name} | Pick={pick}")
            continue

        changed, reason = resolve_row(row, match)

        if changed:
            resolved += 1
            lines.append(
                f"RESOLVED | {date_str} | {game_name} | Pick={pick} | "
                f"Result={row.get('result')} | Final={row.get('final_score')} | {reason}"
            )
        else:
            still_pending += 1
            lines.append(
                f"PENDING | {date_str} | {game_name} | Pick={pick} | "
                f"Score={row.get('final_score')} | {reason}"
            )

    write_rows(rows)

    lines.extend([
        "",
        "Summary:",
        f"- Resolved: {resolved}",
        f"- Still pending: {still_pending}",
        f"- Not found: {not_found}",
        "",
        "Rule: clean moneyline result resolver only. No betting automation."
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
