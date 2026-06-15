# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "107_odds_snapshot_store_report.txt"
SNAPSHOT_DIR = ROOT / ".astrodds" / "odds-snapshots"

ODDS_URL = "http://localhost:3000/api/astrodds/odds/status?sportKey=baseball_mlb&fetch=true"
ET = ZoneInfo("America/Toronto")

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def safe_date_key(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return "unknown"

def main():
    generated_at = datetime.utcnow().isoformat() + "Z"
    today_key = datetime.now(ET).date().isoformat()

    payload = fetch_json(ODDS_URL)
    odds = payload.get("odds") or []

    clean_rows = []
    for row in odds:
        market_type = str(row.get("marketType") or "").lower()

        # Store only useful ASTRODDS markets.
        # Keep h2h/moneyline and totals. Ignore spreads/runline for public strategy.
        if market_type not in ["h2h", "moneyline", "total"]:
            continue

        clean_rows.append({
            "snapshotAt": generated_at,
            "gameDateLocal": safe_date_key(row.get("commenceTime")),
            "gameId": row.get("gameId"),
            "commenceTime": row.get("commenceTime"),
            "awayTeam": row.get("awayTeam"),
            "homeTeam": row.get("homeTeam"),
            "game": row.get("game"),
            "marketType": row.get("marketType"),
            "marketLabel": row.get("marketLabel"),
            "side": row.get("side"),
            "line": row.get("line"),
            "priceAmerican": row.get("priceAmerican"),
            "impliedProbability": row.get("impliedProbability"),
            "bookmaker": row.get("bookmaker"),
            "source": row.get("source"),
        })

    totals = [r for r in clean_rows if str(r.get("marketType")).lower() == "total"]
    moneylines = [r for r in clean_rows if str(r.get("marketType")).lower() in ["h2h", "moneyline"]]

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_file = SNAPSHOT_DIR / f"{today_key}.json"
    latest_file = SNAPSHOT_DIR / "latest.json"

    output = {
        "generatedAt": generated_at,
        "localDate": today_key,
        "mode": "snapshot_only",
        "rules": {
            "storedMarkets": ["moneyline/h2h", "totals"],
            "excluded": ["spreads/runline", "props", "futures"],
            "noTelegram": True,
            "noPublicSignal": True,
        },
        "counts": {
            "rawOddsRows": len(odds),
            "storedRows": len(clean_rows),
            "moneylineRows": len(moneylines),
            "totalRows": len(totals),
        },
        "odds": clean_rows,
    }

    snapshot_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 107 ODDS SNAPSHOT STORE",
        "=" * 56,
        f"Generated UTC: {generated_at}",
        "",
        "Rules:",
        "- Store sportsbook moneyline + totals only.",
        "- Ignore runline/spread.",
        "- No Telegram send.",
        "- No public signal change.",
        "",
        "Counts:",
        f"- rawOddsRows: {len(odds)}",
        f"- storedRows: {len(clean_rows)}",
        f"- moneylineRows: {len(moneylines)}",
        f"- totalRows: {len(totals)}",
        "",
        f"Snapshot: {snapshot_file}",
        f"Latest: {latest_file}",
        "",
        "Rule: snapshot only. Paper/manual only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
