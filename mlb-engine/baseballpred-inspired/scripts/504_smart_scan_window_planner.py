from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OUT_JSON = ASTRO / "ASTRODDS-504-smart-scan-window-plan-latest.json"
REPORT = REPORTS / "504_smart_scan_window_planner_report.txt"

ET = ZoneInfo("America/New_York")

def fetch_mlb_schedule(date_et):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_et}&hydrate=team"
    games = []
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for d in data.get("dates", []):
            for g in d.get("games", []):
                teams = g.get("teams", {})
                away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
                home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
                game_date = g.get("gameDate", "")
                status = (g.get("status") or {}).get("detailedState", "")
                if not away or not home or not game_date:
                    continue
                dt_utc = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
                dt_et = dt_utc.astimezone(ET)
                games.append({
                    "game": f"{away} @ {home}",
                    "awayTeam": away,
                    "homeTeam": home,
                    "gamePk": g.get("gamePk"),
                    "status": status,
                    "gameDateUTC": dt_utc.isoformat(),
                    "gameDateET": dt_et.isoformat(),
                    "startTimeET": dt_et.strftime("%H:%M"),
                })
    except Exception as e:
        return [], str(e)

    games.sort(key=lambda x: x["gameDateET"])
    return games, ""

def within(now, target, minutes=20):
    return abs((now - target).total_seconds()) <= minutes * 60

def add_unique(windows, label, target, scan_type, reason):
    if target is None:
        return
    # round to nearest minute
    target = target.replace(second=0, microsecond=0)
    key = (label, target.isoformat())
    for w in windows:
        if (w["label"], w["targetET"]) == (label, target.isoformat()):
            return
    windows.append({
        "label": label,
        "targetET": target.isoformat(),
        "targetUTC": target.astimezone(timezone.utc).isoformat(),
        "scanType": scan_type,
        "reason": reason,
    })

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    now_et = datetime.now(ET)
    date_et = now_et.strftime("%Y-%m-%d")
    games, error = fetch_mlb_schedule(date_et)

    open_games = []
    for g in games:
        status = str(g.get("status", "")).lower()
        if "final" in status or "game over" in status:
            continue
        open_games.append(g)

    start_times = [datetime.fromisoformat(g["gameDateET"]) for g in open_games]
    early_games = [t for t in start_times if t.hour < 17]
    evening_games = [t for t in start_times if t.hour >= 17]

    windows = []

    # Morning prep is local only: schedule, board, reports, no fresh odds credits.
    morning = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    add_unique(
        windows,
        "morning_local_prep",
        morning,
        "LOCAL_STATUS_ONLY",
        "Build schedule, dashboard, yesterday cleanup and potential slate without spending odds credits."
    )

    # Fresh odds scans: max 3 per day. Existing credit guard remains final protection.
    # Logic: scan near real decision moments only.
    if early_games:
        early_first = min(early_games)
        add_unique(
            windows,
            "early_block_final_pregame",
            early_first - timedelta(minutes=75),
            "FRESH_ODDS_SCAN",
            "Early/afternoon games exist. Scan about 75 minutes before first early game."
        )

    if evening_games:
        evening_first = min(evening_games)
        add_unique(
            windows,
            "evening_block_main",
            evening_first - timedelta(minutes=120),
            "FRESH_ODDS_SCAN",
            "Evening games exist. Main scan about 2 hours before first evening game."
        )
        add_unique(
            windows,
            "evening_block_final_pregame",
            evening_first - timedelta(minutes=45),
            "FRESH_ODDS_SCAN",
            "Final scan about 45 minutes before first evening game."
        )

    # If no split blocks, use first game and last practical decision window.
    if not early_games and not evening_games and start_times:
        first = min(start_times)
        add_unique(windows, "main_pregame_scan", first - timedelta(minutes=90), "FRESH_ODDS_SCAN", "Single slate scan before first game.")
        add_unique(windows, "final_pregame_scan", first - timedelta(minutes=45), "FRESH_ODDS_SCAN", "Final confirmation before first game.")

    # Keep only useful windows for today; keep morning even if passed for reporting.
    fresh_windows = [w for w in windows if w["scanType"] == "FRESH_ODDS_SCAN"]
    # max 3 fresh windows
    fresh_windows = sorted(fresh_windows, key=lambda w: w["targetET"])[:3]
    local_windows = [w for w in windows if w["scanType"] == "LOCAL_STATUS_ONLY"]
    windows = local_windows + fresh_windows

    due = []
    next_window = None
    future_windows = []
    for w in windows:
        target = datetime.fromisoformat(w["targetET"])
        if within(now_et, target, 20):
            due.append(w)
        if target >= now_et - timedelta(minutes=20):
            future_windows.append(w)

    if future_windows:
        next_window = sorted(future_windows, key=lambda w: w["targetET"])[0]

    fresh_due = any(w["scanType"] == "FRESH_ODDS_SCAN" for w in due)
    local_due = any(w["scanType"] == "LOCAL_STATUS_ONLY" for w in due)

    out = {
        "generatedAtUTC": datetime.now(timezone.utc).isoformat(),
        "nowET": now_et.isoformat(),
        "dateET": date_et,
        "scheduleError": error,
        "officialGames": games,
        "openGames": open_games,
        "windows": windows,
        "dueNow": due,
        "freshScanDueNow": fresh_due,
        "localStatusDueNow": local_due,
        "nextWindow": next_window,
        "maxFreshScansPerDay": 3,
        "rule": "Morning is local-only. Fresh odds scans are only near early/evening pregame windows. Credit guard remains final protection."
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 504 SMART SCAN WINDOW PLANNER",
        "=" * 78,
        f"Generated UTC: {out['generatedAtUTC']}",
        f"Now ET: {out['nowET']}",
        f"Date ET: {date_et}",
        f"Schedule error: {error or 'none'}",
        "",
        f"Official games: {len(games)}",
        f"Open games: {len(open_games)}",
        "",
        "Official games:",
    ]

    if games:
        for g in games:
            lines.append(f"- {g['startTimeET']} ET | {g['game']} | status={g['status']} | gamePk={g['gamePk']}")
    else:
        lines.append("- none")

    lines += ["", "Scan plan:"]
    if windows:
        for w in windows:
            target = datetime.fromisoformat(w["targetET"])
            flag = "DUE NOW" if any(d["label"] == w["label"] for d in due) else ""
            lines.append(f"- {target.strftime('%H:%M')} ET | {w['label']} | {w['scanType']} | {flag}")
            lines.append(f"  Reason: {w['reason']}")
    else:
        lines.append("- none")

    lines += [
        "",
        f"Fresh scan due now: {fresh_due}",
        f"Local status due now: {local_due}",
        f"Next window: {next_window['label'] if next_window else 'none'}",
        "",
        "Rules:",
        "- Local status cycle can run anytime; it does not spend odds credits.",
        "- Fresh odds scan should run only when freshScanDueNow=True or when you manually force it.",
        "- Existing credit guard still blocks when daily/monthly limits are reached.",
        "",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
