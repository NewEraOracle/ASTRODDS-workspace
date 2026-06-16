from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, json, os, sys, urllib.parse, urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

LEDGER_CSV = ASTRO / "ASTRODDS-mlb-odds-snapshot-ledger.csv"
LATEST_JSON = ASTRO / "ASTRODDS-mlb-odds-snapshot-latest.json"
REPORT = REPORTS / "179_credit_safe_mlb_odds_collector_report.txt"
CREDIT_JSON = ASTRO / "ASTRODDS-odds-credit-usage-latest.json"

ET = ZoneInfo("America/New_York")

FIELDS = [
    "snapshot_et","snapshot_utc","sport_key","game_id","commence_time","home_team","away_team",
    "bookmaker","market","outcome","price","point","source","notes"
]

def env(name, default=""):
    return os.environ.get(name, default)

def now_et():
    return datetime.now(ET)

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

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def recent_snapshot_exists(minutes=45):
    rows = read_csv(LEDGER_CSV)
    if not rows:
        return False, None
    latest = rows[-1].get("snapshot_et", "")
    try:
        dt = datetime.fromisoformat(latest)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET)
        age = now_et() - dt.astimezone(ET)
        return age <= timedelta(minutes=minutes), latest
    except Exception:
        return False, latest

def count_used_today():
    usage = load_json(CREDIT_JSON, {"date": now_et().date().isoformat(), "estimatedRequests": 0, "events": []})
    if usage.get("date") != now_et().date().isoformat():
        usage = {"date": now_et().date().isoformat(), "estimatedRequests": 0, "events": []}
    return usage

def record_usage(note):
    usage = count_used_today()
    usage["estimatedRequests"] = int(usage.get("estimatedRequests", 0)) + 1
    usage.setdefault("events", []).append({"time_et": now_et().isoformat(), "note": note})
    save_json(CREDIT_JSON, usage)

def fetch_odds():
    api_key = env("ODDS_API_KEY") or env("THE_ODDS_API_KEY") or env("ASTRODDS_ODDS_API_KEY")
    if not api_key:
        return None, "MISSING_ODDS_API_KEY"

    sport = env("ASTRODDS_ODDS_SPORT_KEY", "baseball_mlb")
    regions = env("ASTRODDS_ODDS_REGIONS", "us")
    markets = env("ASTRODDS_ODDS_MARKETS", "h2h,totals")
    odds_format = env("ASTRODDS_ODDS_FORMAT", "american")

    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }

    # Optional bookmaker restriction if user wants to save noise.
    bookmakers = env("ASTRODDS_ODDS_BOOKMAKERS", "")
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ASTRODDS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        headers = dict(resp.headers)
    return {"sport": sport, "data": data, "headers": headers}, "OK"

def flatten(snapshot):
    snap_et = now_et()
    snap_utc = datetime.utcnow().isoformat() + "Z"
    sport = snapshot["sport"]
    out = []

    for game in snapshot.get("data", []):
        game_id = game.get("id", "")
        commence = game.get("commence_time", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        for bm in game.get("bookmakers", []):
            bm_key = bm.get("key") or bm.get("title", "")
            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    out.append({
                        "snapshot_et": snap_et.isoformat(),
                        "snapshot_utc": snap_utc,
                        "sport_key": sport,
                        "game_id": game_id,
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker": bm_key,
                        "market": mkey,
                        "outcome": outcome.get("name", ""),
                        "price": outcome.get("price", ""),
                        "point": outcome.get("point", ""),
                        "source": "the_odds_api_live",
                        "notes": "",
                    })
    return out

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    dry_run = os.environ.get("ASTRODDS_ODDS_COLLECTOR_DRY_RUN", "").lower() in ("1","true","yes")
    force = os.environ.get("ASTRODDS_ODDS_COLLECTOR_FORCE", "").lower() in ("1","true","yes")
    min_gap = int(os.environ.get("ASTRODDS_ODDS_MIN_GAP_MINUTES", "45"))
    daily_cap = int(os.environ.get("ASTRODDS_ODDS_DAILY_REQUEST_CAP", "4"))

    usage = count_used_today()
    recent, latest = recent_snapshot_exists(min_gap)

    lines = [
        "ASTRODDS 179 CREDIT-SAFE MLB ODDS COLLECTOR",
        "=" * 68,
        f"Generated ET: {now_et().isoformat()}",
        "",
        "Rules:",
        "- Pulls MLB odds only.",
        "- Markets: h2h + totals by default.",
        "- Stores snapshots to local ledger.",
        "- Skips if recent snapshot exists unless forced.",
        "- No betting automation.",
        "",
        f"Dry run: {dry_run}",
        f"Force: {force}",
        f"Recent snapshot exists: {recent} latest={latest}",
        f"Estimated requests today: {usage.get('estimatedRequests', 0)} / cap {daily_cap}",
    ]

    if recent and not force:
        lines += ["", "SKIPPED: recent snapshot exists."]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    if int(usage.get("estimatedRequests", 0)) >= daily_cap and not force:
        lines += ["", "SKIPPED: daily request cap reached."]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    if dry_run:
        lines += ["", "DRY RUN ONLY: no request sent."]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    try:
        snapshot, status = fetch_odds()
    except Exception as exc:
        snapshot, status = None, f"ERROR: {exc}"

    if status != "OK":
        lines += ["", f"STOP: {status}", "Set ODDS_API_KEY / THE_ODDS_API_KEY / ASTRODDS_ODDS_API_KEY in .env.local if missing."]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    new_rows = flatten(snapshot)
    old_rows = read_csv(LEDGER_CSV)
    all_rows = old_rows + new_rows
    write_csv(LEDGER_CSV, all_rows)

    save_json(LATEST_JSON, {
        "generatedAtEt": now_et().isoformat(),
        "sport": snapshot["sport"],
        "games": len(snapshot.get("data", [])),
        "rows": len(new_rows),
        "headers": {k: v for k, v in snapshot.get("headers", {}).items() if "x-requests" in k.lower()},
        "data": snapshot.get("data", []),
    })

    record_usage(f"odds snapshot rows={len(new_rows)} games={len(snapshot.get('data', []))}")

    lines += [
        "",
        "COLLECTED:",
        f"- games: {len(snapshot.get('data', []))}",
        f"- rows added: {len(new_rows)}",
        f"- ledger rows total: {len(all_rows)}",
        f"- CSV: {LEDGER_CSV}",
        f"- JSON: {LATEST_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
