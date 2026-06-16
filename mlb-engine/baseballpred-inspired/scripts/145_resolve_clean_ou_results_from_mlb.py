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

OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
REPORT = REPORTS / "145_resolve_clean_ou_results_from_mlb_report.txt"

ET = ZoneInfo("America/New_York")

TEAM_ALIASES = {
    "athletics": "athletics",
    "oakland athletics": "athletics",
    "a's": "athletics",
    "blue jays": "toronto blue jays",
    "toronto blue jays": "toronto blue jays",
    "red sox": "boston red sox",
    "boston red sox": "boston red sox",
    "orioles": "baltimore orioles",
    "baltimore orioles": "baltimore orioles",
    "mariners": "seattle mariners",
    "seattle mariners": "seattle mariners",
    "white sox": "chicago white sox",
    "chicago white sox": "chicago white sox",
    "yankees": "new york yankees",
    "new york yankees": "new york yankees",
    "guardians": "cleveland guardians",
    "cleveland guardians": "cleveland guardians",
    "brewers": "milwaukee brewers",
    "milwaukee brewers": "milwaukee brewers",
    "royals": "kansas city royals",
    "kansas city royals": "kansas city royals",
    "nationals": "washington nationals",
    "washington nationals": "washington nationals",
    "tigers": "detroit tigers",
    "detroit tigers": "detroit tigers",
    "astros": "houston astros",
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
    for sep in [" vs. ", " vs ", " @ "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return norm_team(a), norm_team(h)
    return "", ""

def read_rows():
    if not OU_CSV.exists():
        return []
    with OU_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_rows(rows):
    if not rows:
        return

    base_fields = [
        "date", "game", "pick", "result", "line", "projected", "edge_runs",
        "price", "stake", "status", "grade", "final_score", "total_runs",
        "resolved_at", "notes"
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

    backup = OU_CSV.with_suffix(".before-145-resolve.csv")
    try:
        if OU_CSV.exists():
            OU_CSV.replace(backup)
    except Exception:
        pass

    with OU_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def mlb_schedule(date_str):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"sportId": 1, "date": date_str, "hydrate": "linescore"}
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
    coded = str(status.get("codedGameState", "")).upper()
    return abstract_state == "final" or "final" in detailed_state or coded in ("F", "FT", "FR")

def find_matching_game(row, schedule_games):
    row_away, row_home = parse_game_teams(row.get("game"))
    for g in schedule_games:
        teams = g.get("teams", {})
        away_name = norm_team(teams.get("away", {}).get("team", {}).get("name", ""))
        home_name = norm_team(teams.get("home", {}).get("team", {}).get("name", ""))

        exact = row_away and row_home and away_name == row_away and home_name == row_home
        loose = row_away in (away_name, home_name) and row_home in (away_name, home_name)

        if exact or loose:
            return g
    return None

def parse_line(row):
    raw = str(row.get("line", "")).strip()
    if not raw:
        raw = str(row.get("pick", "")).replace("Over", "").replace("Under", "").strip()
    try:
        return float(raw)
    except Exception:
        return None

def resolve_row(row, game_obj):
    teams = game_obj.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_score = away.get("score")
    home_score = home.get("score")

    if away_score is None or home_score is None:
        return False, "missing score"

    try:
        away_score = int(away_score)
        home_score = int(home_score)
    except Exception:
        return False, "bad score"

    total = away_score + home_score
    line = parse_line(row)

    row["final_score"] = f"{away_score}-{home_score}"
    row["total_runs"] = str(total)

    if not is_final(game_obj):
        row["result"] = "pending"
        row["resolved_at"] = ""
        return False, "not final"

    if line is None:
        return False, "missing line"

    pick = str(row.get("pick", "")).strip().lower()
    if pick.startswith("over"):
        if total > line:
            row["result"] = "win"
        elif total < line:
            row["result"] = "loss"
        else:
            row["result"] = "push"
    elif pick.startswith("under"):
        if total < line:
            row["result"] = "win"
        elif total > line:
            row["result"] = "loss"
        else:
            row["result"] = "push"
    else:
        return False, "bad pick"

    row["resolved_at"] = now_et()
    return True, f"total={total} line={line}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    rows = read_rows()
    pending_rows = [
        r for r in rows
        if str(r.get("status", "")).strip() == "clean_ou_aplus"
        and str(r.get("result", "")).strip().lower() in ("pending", "", "tbd")
    ]

    lines = [
        "ASTRODDS 145 RESOLVE CLEAN O/U RESULTS FROM MLB",
        "=" * 64,
        f"Generated ET: {now_et()}",
        f"CSV: {OU_CSV}",
        f"Rows total: {len(rows)}",
        f"Pending O/U rows: {len(pending_rows)}",
        "",
    ]

    if not pending_rows:
        lines.append("No pending O/U rows to resolve.")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    schedules = {}
    resolved = 0
    still_pending = 0
    not_found = 0

    for row in pending_rows:
        date_str = str(row.get("date", "")).strip()
        game = row.get("game", "")
        pick = row.get("pick", "")

        if date_str not in schedules:
            try:
                schedules[date_str] = mlb_schedule(date_str)
            except Exception as exc:
                lines.append(f"ERROR schedule fetch failed for {date_str}: {exc}")
                schedules[date_str] = []

        match = find_matching_game(row, schedules[date_str])
        if not match:
            not_found += 1
            lines.append(f"NOT FOUND | {date_str} | {game} | {pick}")
            continue

        changed, reason = resolve_row(row, match)
        if changed:
            resolved += 1
            lines.append(
                f"RESOLVED | {date_str} | {game} | {pick} | "
                f"Result={row.get('result')} | Final={row.get('final_score')} | "
                f"Total={row.get('total_runs')} | {reason}"
            )
        else:
            still_pending += 1
            lines.append(
                f"PENDING | {date_str} | {game} | {pick} | "
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
        "Rule: clean O/U result resolver only. No betting automation."
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
