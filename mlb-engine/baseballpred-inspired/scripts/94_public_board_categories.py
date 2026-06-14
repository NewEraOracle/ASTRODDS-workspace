# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "94_public_board_categories_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-public-board-categories-latest.json"

API_URL = "http://localhost:3000/api/astrodds/best-bets/today"
ET = ZoneInfo("America/Toronto")

def fetch_api():
    with urllib.request.urlopen(API_URL, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def et_date_key(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return None

def is_today(row):
    return et_date_key(row.get("date")) == datetime.now(ET).date().isoformat()

def is_future(row):
    row_key = et_date_key(row.get("date"))
    today = datetime.now(ET).date().isoformat()
    return bool(row_key and row_key > today)

def is_pregame(row):
    return str(row.get("gameStatus") or "").lower() == "pre_game"

def is_connected(row):
    return row.get("marketConnected") is True and fnum(row.get("marketProbability")) is not None

def key(row):
    return "|".join([
        str(row.get("date") or ""),
        str(row.get("awayTeam") or ""),
        str(row.get("homeTeam") or ""),
        str(row.get("selectedSide") or ""),
    ]).lower()

def pct(value):
    n = fnum(value)
    return "-" if n is None else f"{n * 100:.2f}%"

def price(value):
    n = fnum(value)
    return "-" if n is None else f"${n:.2f}"

def edge_pct(row):
    edge = fnum(row.get("edge"))
    return "-" if edge is None else f"{edge * 100:.2f}%"

def clean_row(row, category, stake, reason):
    return {
        "category": category,
        "stake": stake,
        "date": row.get("date"),
        "game": f"{row.get('awayTeam')} @ {row.get('homeTeam')}",
        "pick": row.get("selectedSide"),
        "gameStatus": row.get("gameStatus"),
        "marketConnected": row.get("marketConnected"),
        "market": fnum(row.get("marketProbability")),
        "model": fnum(row.get("calibratedProbability")),
        "edge": fnum(row.get("edge")),
        "matchConfidence": row.get("matchConfidence"),
        "riskLevel": row.get("riskLevel"),
        "reason": reason,
    }

def main():
    data = fetch_api()

    official = data.get("officialPicks") or []
    leans = data.get("moneylineLeans") or []
    diagnostics = data.get("diagnostics") or {}

    used = set()

    # A PICK = strict today-only.
    a_picks = []
    for row in official:
        edge = fnum(row.get("edge"))
        model = fnum(row.get("calibratedProbability"))

        if not is_today(row): 
            continue
        if not is_pregame(row): 
            continue
        if not is_connected(row): 
            continue
        if edge is None or edge < 0.10:
            continue
        if model is None or model < 0.60:
            continue

        used.add(key(row))
        a_picks.append(clean_row(
            row,
            "A_PICK",
            "5% bankroll",
            "Best same-day value spot with clean market price and strong positive edge.",
        ))

    # VALUE LEAN = same-day only, smaller stake.
    value_leans = []
    for row in leans:
        edge = fnum(row.get("edge"))
        model = fnum(row.get("calibratedProbability"))

        if key(row) in used:
            continue
        if not is_today(row):
            continue
        if not is_pregame(row):
            continue
        if not is_connected(row):
            continue
        if edge is None or edge < 0.05:
            continue
        if model is None or model < 0.58:
            continue

        used.add(key(row))
        value_leans.append(clean_row(
            row,
            "VALUE_LEAN",
            "1-2% max",
            "Same-day value angle with clean market price, but not strong enough for A Pick.",
        ))

    # ACTION LEAN = same-day only, smallest stake.
    action_leans = []
    for row in leans:
        edge = fnum(row.get("edge"))
        model = fnum(row.get("calibratedProbability"))

        if key(row) in used:
            continue
        if not is_today(row):
            continue
        if not is_pregame(row):
            continue
        if not is_connected(row):
            continue
        if edge is None or edge < 0.03:
            continue
        if model is None or model < 0.58:
            continue

        used.add(key(row))
        action_leans.append(clean_row(
            row,
            "ACTION_LEAN",
            "0.5-1% max",
            "Same-day small edge. Action only, not a main bet.",
        ))

    # UPCOMING WATCHLIST = future only, no stake.
    upcoming = []
    for row in leans:
        model = fnum(row.get("calibratedProbability"))

        if not is_future(row):
            continue
        if model is None or model < 0.58:
            continue

        upcoming.append(clean_row(
            row,
            "UPCOMING_WATCHLIST",
            "No stake today",
            "Future game. Do not bet today. Re-check when it becomes same-day.",
        ))

    a_picks.sort(key=lambda r: r.get("edge") or 0, reverse=True)
    value_leans.sort(key=lambda r: r.get("edge") or 0, reverse=True)
    action_leans.sort(key=lambda r: r.get("edge") or 0, reverse=True)
    upcoming.sort(key=lambda r: (str(r.get("date") or ""), -(r.get("model") or 0)))

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "rules": {
            "A_PICK": "today only, pre-game, market connected, edge >= 10%, stake 5%",
            "VALUE_LEAN": "today only, pre-game, market connected, edge >= 5%, stake 1-2%",
            "ACTION_LEAN": "today only, pre-game, market connected, edge >= 3%, stake 0.5-1%",
            "UPCOMING_WATCHLIST": "future games only, no stake today",
        },
        "counts": {
            "aPick": len(a_picks),
            "valueLean": len(value_leans),
            "actionLean": len(action_leans),
            "upcomingWatchlist": len(upcoming),
            "scanGamesFound": diagnostics.get("scanGamesFound"),
            "rowsWithRealPrice": diagnostics.get("rowsWithRealPrice"),
            "moneylinePricesFound": diagnostics.get("moneylinePricesFound"),
            "polymarketCleanMoneylineFound": diagnostics.get("polymarketCleanMoneylineFound"),
        },
        "aPicks": a_picks,
        "valueLeans": value_leans[:5],
        "actionLeans": action_leans[:5],
        "upcomingWatchlist": upcoming[:12],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 94 PUBLIC BOARD CATEGORIES",
        "=" * 56,
        f"Generated UTC: {output['generatedAt']}",
        "",
        "Rules:",
        "- A PICK = today only / 5%",
        "- VALUE LEAN = today only / 1-2%",
        "- ACTION LEAN = today only / 0.5-1%",
        "- UPCOMING WATCHLIST = no stake today",
        "",
        "Counts:",
    ]

    for k, v in output["counts"].items():
        lines.append(f"- {k}: {v}")

    def add_section(title, rows):
        lines.append("")
        lines.append(title)
        if not rows:
            lines.append("- none")
            return
        for r in rows:
            lines.append(
                f"- {r['pick']} | {r['game']} | Date={r['date']} | "
                f"Market={price(r.get('market'))} | Model={pct(r.get('model'))} | "
                f"Edge={edge_pct(r)} | Stake={r['stake']}"
            )

    add_section("A PICK:", a_picks)
    add_section("VALUE LEAN:", value_leans[:5])
    add_section("ACTION LEAN:", action_leans[:5])
    add_section("UPCOMING WATCHLIST - NOT BET TODAY:", upcoming[:12])

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: Paper/manual only. No real-money automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
