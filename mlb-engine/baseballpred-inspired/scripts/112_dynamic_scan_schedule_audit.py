# -*- coding: utf-8 -*-
"""
ASTRODDS 112 - Dynamic Scan Schedule Audit

Audit-only module.
- Uses MLB StatsAPI schedule only (free)
- Recommends scan times based on today's first pitch / late slate
- Protects The Odds API credits by limiting odds scans
- Does NOT run scans, Telegram, or public signals
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "112_dynamic_scan_schedule_audit_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-dynamic-scan-schedule-latest.json"

ET = ZoneInfo("America/Toronto")

MAX_ODDS_SCANS_PER_DAY = 3

def fetch_json(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def dt_et(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET)

def today_schedule():
    today = datetime.now(ET).date()
    params = urllib.parse.urlencode({
        "sportId": 1,
        "date": today.isoformat(),
        "hydrate": "team"
    })
    url = f"https://statsapi.mlb.com/api/v1/schedule?{params}"
    data = fetch_json(url)

    games = []
    for block in data.get("dates", []):
        for g in block.get("games", []):
            teams = g.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            away_team = ((away.get("team") or {}).get("name"))
            home_team = ((home.get("team") or {}).get("name"))
            game_dt = dt_et(g.get("gameDate"))
            games.append({
                "gamePk": g.get("gamePk"),
                "gameDate": g.get("gameDate"),
                "localTime": game_dt.isoformat(),
                "awayTeam": away_team,
                "homeTeam": home_team,
                "game": f"{away_team} @ {home_team}",
                "state": ((g.get("status") or {}).get("detailedState")),
            })

    games.sort(key=lambda x: x["localTime"])
    return games

def add_scan(scans, label, when_dt, odds_scan, reason):
    now = datetime.now(ET)
    scans.append({
        "label": label,
        "timeLocal": when_dt.isoformat(),
        "timeLabel": when_dt.strftime("%I:%M %p").lstrip("0"),
        "isPast": when_dt < now,
        "oddsScan": bool(odds_scan),
        "contextScan": True,
        "reason": reason,
    })

def build_schedule(games):
    now = datetime.now(ET)
    today = now.date()

    scans = []

    if not games:
        return scans, {
            "firstGameLocal": None,
            "lastGameLocal": None,
            "lateSlateStartLocal": None,
        }

    first = dt_et(games[0]["gameDate"])
    last = dt_et(games[-1]["gameDate"])

    # Fixed light checks only if they are useful.
    morning = datetime.combine(today, time(10, 30), tzinfo=ET)
    market = datetime.combine(today, time(14, 0), tzinfo=ET)

    if first.time() <= time(14, 30):
        # Early slate: shift earlier.
        add_scan(scans, "early_morning_check", max(morning, first - timedelta(hours=3)), True, "Early slate: initial odds/context before early games.")
        add_scan(scans, "early_main_slate_scan", first - timedelta(minutes=90), True, "Main scan 90 minutes before first game.")
        add_scan(scans, "early_lineup_confirmation", first - timedelta(minutes=35), True, "Lineup confirmation 35 minutes before first game.")
    else:
        add_scan(scans, "morning_check", morning, True, "Light odds snapshot + schedule check.")
        add_scan(scans, "market_check", market, True, "Market check / watchlist, not forced picks.")
        add_scan(scans, "main_slate_scan", first - timedelta(minutes=90), True, "Main scan 90 minutes before first game.")
        add_scan(scans, "lineup_confirmation", first - timedelta(minutes=35), True, "Lineup confirmation 35 minutes before first game.")

    # Late slate: only if there are games at least 2h after first pitch.
    late_games = [dt_et(g["gameDate"]) for g in games if dt_et(g["gameDate"]) >= first + timedelta(hours=2)]
    late_start = min(late_games) if late_games else None

    if late_start:
        add_scan(scans, "late_slate_scan", late_start - timedelta(minutes=60), True, "Late-slate scan 60 minutes before late games.")

    # De-duplicate by rounded minute and sort.
    unique = {}
    for s in scans:
        key = s["timeLocal"][:16] + "|" + s["label"]
        unique[key] = s
    scans = sorted(unique.values(), key=lambda x: x["timeLocal"])

    # Protect Odds API credits: only first MAX_ODDS_SCANS_PER_DAY future odds scans stay true.
    future_odds = [s for s in scans if s["oddsScan"] and not s["isPast"]]
    if len(future_odds) > MAX_ODDS_SCANS_PER_DAY:
        keep_ids = set(id(s) for s in future_odds[:MAX_ODDS_SCANS_PER_DAY])
        for s in scans:
            if s["oddsScan"] and not s["isPast"] and id(s) not in keep_ids:
                s["oddsScan"] = False
                s["reason"] += " Converted to context-only to protect odds credits."

    meta = {
        "firstGameLocal": first.isoformat(),
        "lastGameLocal": last.isoformat(),
        "lateSlateStartLocal": late_start.isoformat() if late_start else None,
    }

    return scans, meta

def main():
    generated = datetime.utcnow().isoformat() + "Z"
    games = today_schedule()
    scans, meta = build_schedule(games)

    counts = {
        "gamesToday": len(games),
        "recommendedScans": len(scans),
        "futureOddsScans": len([s for s in scans if s["oddsScan"] and not s["isPast"]]),
        "futureContextOnlyScans": len([s for s in scans if not s["oddsScan"] and not s["isPast"]]),
        "pastScans": len([s for s in scans if s["isPast"]]),
        "maxOddsScansPerDay": MAX_ODDS_SCANS_PER_DAY,
    }

    output = {
        "generatedAt": generated,
        "mode": "audit_only",
        "rules": {
            "noTelegram": True,
            "noPublicSignal": True,
            "doesNotRunScans": True,
            "creditProtection": f"Max {MAX_ODDS_SCANS_PER_DAY} future odds scans per day.",
            "freeContext": "MLB/weather/lineup/bullpen modules can run more often because they do not use The Odds API credits.",
        },
        "meta": meta,
        "counts": counts,
        "games": games,
        "recommendedScans": scans,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 112 DYNAMIC SCAN SCHEDULE AUDIT",
        "=" * 62,
        f"Generated UTC: {generated}",
        "",
        "Rules:",
        "- Audit only.",
        "- Does not run scans.",
        "- Dynamic schedule based on first pitch / late slate.",
        f"- Protects odds credits: max {MAX_ODDS_SCANS_PER_DAY} future odds scans/day.",
        "- Context-only scans can run more often because they use free sources.",
        "",
        "Counts:",
    ]

    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    lines += [
        "",
        f"First game local: {meta.get('firstGameLocal') or '-'}",
        f"Last game local: {meta.get('lastGameLocal') or '-'}",
        f"Late slate start local: {meta.get('lateSlateStartLocal') or '-'}",
        "",
        "Recommended scans:",
    ]

    if not scans:
        lines.append("- none")
    else:
        for s in scans:
            scan_type = "ODDS+CONTEXT" if s["oddsScan"] else "CONTEXT_ONLY"
            past = "past" if s["isPast"] else "future"
            lines.append(f"- {s['label']} | {s['timeLabel']} ET | {scan_type} | {past} | {s['reason']}")

    lines += ["", "Games today:"]
    for g in games[:25]:
        gt = dt_et(g["gameDate"]).strftime("%I:%M %p").lstrip("0")
        lines.append(f"- {gt} ET | {g['game']} | {g.get('state') or '-'}")

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: schedule audit only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()

