from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import json
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

MARKET_CSV = ASTRO / "ASTRODDS-historical-market-lines-template.csv"
REPORT = REPORTS / "186_resolve_market_lines_results_from_mlb_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-market-lines-resolve-latest.json"

FIELDS = [
    "date","sport","game","market","pick","open_line","close_line",
    "open_price","close_price","final_score","result","source","notes"
]

ET = ZoneInfo("America/New_York")

TEAM_ALIASES = {
    "arizona diamondbacks": "arizona diamondbacks",
    "athletics": "athletics",
    "oakland athletics": "athletics",
    "sacramento athletics": "athletics",
    "atlanta braves": "atlanta braves",
    "baltimore orioles": "baltimore orioles",
    "boston red sox": "boston red sox",
    "chicago cubs": "chicago cubs",
    "chicago white sox": "chicago white sox",
    "cincinnati reds": "cincinnati reds",
    "cleveland guardians": "cleveland guardians",
    "colorado rockies": "colorado rockies",
    "detroit tigers": "detroit tigers",
    "houston astros": "houston astros",
    "kansas city royals": "kansas city royals",
    "los angeles angels": "los angeles angels",
    "la angels": "los angeles angels",
    "los angeles dodgers": "los angeles dodgers",
    "la dodgers": "los angeles dodgers",
    "miami marlins": "miami marlins",
    "milwaukee brewers": "milwaukee brewers",
    "minnesota twins": "minnesota twins",
    "new york mets": "new york mets",
    "ny mets": "new york mets",
    "new york yankees": "new york yankees",
    "ny yankees": "new york yankees",
    "philadelphia phillies": "philadelphia phillies",
    "pittsburgh pirates": "pittsburgh pirates",
    "san diego padres": "san diego padres",
    "san francisco giants": "san francisco giants",
    "seattle mariners": "seattle mariners",
    "st louis cardinals": "st louis cardinals",
    "st. louis cardinals": "st louis cardinals",
    "tampa bay rays": "tampa bay rays",
    "texas rangers": "texas rangers",
    "toronto blue jays": "toronto blue jays",
    "washington nationals": "washington nationals",
}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return TEAM_ALIASES.get(s, s)

def parse_game(game):
    g = str(game or "")
    for sep in [" @ ", " vs. ", " vs "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return norm(a), norm(h)
    return "", ""

def fnum(v, default=None):
    try:
        s = str(v).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(FIELDS)
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def fetch_schedule(date):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"sportId": 1, "date": date}
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "ASTRODDS/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [g for d in data.get("dates", []) for g in d.get("games", [])]

def status_final(game):
    status = game.get("status", {})
    abstract = str(status.get("abstractGameState", "")).lower()
    detailed = str(status.get("detailedState", "")).lower()
    coded = str(status.get("codedGameState", "")).upper()
    danger = ["postponed", "suspended", "delayed", "cancelled", "canceled", "rescheduled"]
    if any(x in detailed for x in danger):
        return False, "KEEP_PENDING", detailed or coded
    if abstract == "final" or "final" in detailed or coded in ("F", "FT", "FR"):
        return True, "FINAL", detailed or coded
    return False, "KEEP_PENDING", detailed or coded

def build_game_index(dates):
    idx = {}
    statuses = {}
    errors = []
    for date in sorted(dates):
        try:
            games = fetch_schedule(date)
        except Exception as exc:
            errors.append(f"{date}: {exc}")
            continue
        for g in games:
            teams = g.get("teams", {})
            away = teams.get("away", {})
            home = teams.get("home", {})
            away_name = away.get("team", {}).get("name", "")
            home_name = home.get("team", {}).get("name", "")
            key = (date, norm(away_name), norm(home_name))
            is_final, state, detail = status_final(g)
            away_score = away.get("score")
            home_score = home.get("score")
            idx[key] = {
                "date": date,
                "away": away_name,
                "home": home_name,
                "away_norm": norm(away_name),
                "home_norm": norm(home_name),
                "away_score": away_score,
                "home_score": home_score,
                "final": is_final,
                "state": state,
                "detail": detail,
                "gamePk": g.get("gamePk"),
            }
            statuses[f"{date}|{away_name}@{home_name}"] = idx[key]
    return idx, statuses, errors

def find_game(row, index):
    date = str(row.get("date", ""))[:10]
    away, home = parse_game(row.get("game", ""))
    if not date or not away or not home:
        return None
    exact = index.get((date, away, home))
    if exact:
        return exact
    # Sometimes source uses reversed game text.
    reverse = index.get((date, home, away))
    if reverse:
        return reverse
    # Fuzzy same date.
    for (d, a, h), g in index.items():
        if d != date:
            continue
        if {a, h} == {away, home}:
            return g
    return None

def resolve_row(row, game):
    if not game:
        return row, "NO_MATCH"
    if not game.get("final"):
        row["notes"] = append_note(row.get("notes", ""), f"MLB status={game.get('detail')}; kept pending")
        return row, "PENDING"

    away_score = int(game.get("away_score") or 0)
    home_score = int(game.get("home_score") or 0)
    total = away_score + home_score
    final_score = f"{game.get('away')} {away_score} - {game.get('home')} {home_score}"
    row["final_score"] = final_score

    market = str(row.get("market", "")).lower()
    pick = str(row.get("pick", "")).strip()
    pick_norm = norm(pick)
    close_line = fnum(row.get("close_line"), fnum(row.get("open_line"), None))

    if market in ("ou", "total", "totals", "over_under") or "total" in market:
        if close_line is None:
            return row, "NO_LINE"
        if pick_norm in ("over",) or pick_norm.startswith("over"):
            if total > close_line:
                row["result"] = "win"
            elif total < close_line:
                row["result"] = "loss"
            else:
                row["result"] = "push"
        elif pick_norm in ("under",) or pick_norm.startswith("under"):
            if total < close_line:
                row["result"] = "win"
            elif total > close_line:
                row["result"] = "loss"
            else:
                row["result"] = "push"
        else:
            return row, "UNKNOWN_OU_PICK"
        row["notes"] = append_note(row.get("notes", ""), f"resolved_total_runs={total}; close_line={close_line}; gamePk={game.get('gamePk')}")
        return row, "RESOLVED"

    if market in ("moneyline", "h2h", "ml") or "money" in market:
        winner = game.get("away") if away_score > home_score else game.get("home")
        winner_norm = norm(winner)
        if pick_norm == winner_norm:
            row["result"] = "win"
        else:
            row["result"] = "loss"
        row["notes"] = append_note(row.get("notes", ""), f"resolved_winner={winner}; gamePk={game.get('gamePk')}")
        return row, "RESOLVED"

    return row, "UNKNOWN_MARKET"

def append_note(old, new):
    old = str(old or "")
    if new in old:
        return old
    return (old + " | " + new).strip(" |")

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = read_csv(MARKET_CSV)
    pending = [r for r in rows if str(r.get("result", "")).lower() not in ("win", "loss", "push")]
    dates = {str(r.get("date", ""))[:10] for r in pending if r.get("date")}
    # Include yesterday/today to handle timezone / late games.
    today = datetime.now(ET).date()
    dates.add(today.isoformat())
    dates.add((today - timedelta(days=1)).isoformat())

    index, statuses, errors = build_game_index(dates)

    counts = {"resolved": 0, "pending": 0, "no_match": 0, "unknown": 0, "no_line": 0}
    changed = 0
    updated = []

    new_rows = []
    for row in rows:
        if str(row.get("result", "")).lower() in ("win", "loss", "push"):
            new_rows.append(row)
            continue
        game = find_game(row, index)
        before = dict(row)
        row, status = resolve_row(row, game)
        if status == "RESOLVED":
            counts["resolved"] += 1
        elif status == "PENDING":
            counts["pending"] += 1
        elif status == "NO_MATCH":
            counts["no_match"] += 1
        elif status == "NO_LINE":
            counts["no_line"] += 1
        else:
            counts["unknown"] += 1
        if row != before:
            changed += 1
            updated.append(row)
        new_rows.append(row)

    write_csv(MARKET_CSV, new_rows)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "csv": str(MARKET_CSV),
        "rows": len(rows),
        "pendingBefore": len(pending),
        "changedRows": changed,
        "counts": counts,
        "datesChecked": sorted(dates),
        "scheduleErrors": errors[:20],
        "updatedPreview": updated[:20],
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 186 RESOLVE MARKET LINES RESULTS FROM MLB",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        f"CSV: {MARKET_CSV}",
        "",
        f"Rows total: {len(rows)}",
        f"Pending before: {len(pending)}",
        f"Changed rows: {changed}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")
    lines += ["", f"Dates checked: {sorted(dates)}", f"Schedule errors: {len(errors)}", "", "Updated preview:"]
    for r in updated[:20]:
        lines.append(f"- {r.get('date')} | {r.get('result','')} | {r.get('market')} | {r.get('pick')} | {r.get('game')} | {r.get('final_score','')}")
    lines += ["", "Rule:", "- Only resolves rows when MLB status is final.", "- Postponed/suspended/delayed stays pending.", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
