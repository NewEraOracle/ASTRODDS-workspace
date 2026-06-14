# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
REPORT = BASE / "reports" / "85_market_price_matching_audit_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-market-price-matching-audit-latest.json"

API_URL = "http://localhost:3000/api/astrodds/best-bets/today"

def fetch_api():
    with urllib.request.urlopen(API_URL, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def is_today(row):
    date = str(row.get("date") or "")
    return date.startswith(datetime.utcnow().date().isoformat())

def is_pregame(row):
    return str(row.get("gameStatus") or "").lower() == "pre_game"

def main():
    data = fetch_api()

    rows = data.get("bestBetRows") or []
    official = data.get("officialPicks") or []
    leans = data.get("moneylineLeans") or []
    no_bets = data.get("noBets") or []
    diagnostics = data.get("diagnostics") or {}

    today_rows = [r for r in rows if is_today(r)]
    today_pregame = [r for r in today_rows if is_pregame(r)]
    today_pregame_model = [
        r for r in today_pregame
        if fnum(r.get("calibratedProbability")) is not None
    ]
    today_pregame_no_price = [
        r for r in today_pregame_model
        if not r.get("marketConnected") or fnum(r.get("marketProbability")) is None
    ]
    today_pregame_with_price = [
        r for r in today_pregame_model
        if r.get("marketConnected") and fnum(r.get("marketProbability")) is not None
    ]

    model_strong_no_price = [
        r for r in today_pregame_no_price
        if (fnum(r.get("calibratedProbability")) or 0) >= 0.60
    ]

    possible_value_no_price = []
    for r in today_pregame_no_price:
        cp = fnum(r.get("calibratedProbability"))
        if cp is not None and cp >= 0.58:
            possible_value_no_price.append({
                "gameId": r.get("gameId"),
                "date": r.get("date"),
                "homeTeam": r.get("homeTeam"),
                "awayTeam": r.get("awayTeam"),
                "selectedSide": r.get("selectedSide"),
                "status": r.get("status"),
                "gameStatus": r.get("gameStatus"),
                "calibratedProbability": cp,
                "modelScore": r.get("modelScore"),
                "dataQuality": r.get("dataQuality"),
                "mainReason": r.get("mainReason"),
                "blockReasons": r.get("blockReasons"),
            })

    priced_today = []
    for r in today_pregame_with_price:
        mp = fnum(r.get("marketProbability"))
        cp = fnum(r.get("calibratedProbability"))
        edge = None if mp is None or cp is None else cp - mp
        priced_today.append({
            "gameId": r.get("gameId"),
            "date": r.get("date"),
            "homeTeam": r.get("homeTeam"),
            "awayTeam": r.get("awayTeam"),
            "selectedSide": r.get("selectedSide"),
            "status": r.get("status"),
            "gameStatus": r.get("gameStatus"),
            "marketConnected": r.get("marketConnected"),
            "marketProbability": mp,
            "calibratedProbability": cp,
            "edge": edge,
            "priceSourceUsed": r.get("priceSourceUsed"),
            "mainReason": r.get("mainReason"),
        })

    priced_today.sort(key=lambda x: x.get("edge") if x.get("edge") is not None else -999, reverse=True)
    possible_value_no_price.sort(key=lambda x: x.get("calibratedProbability") or 0, reverse=True)

    audit = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "apiStatus": data.get("status"),
        "diagnostics": diagnostics,
        "counts": {
            "bestBetRows": len(rows),
            "officialPicks": len(official),
            "moneylineLeans": len(leans),
            "noBets": len(no_bets),
            "todayRows": len(today_rows),
            "todayPreGame": len(today_pregame),
            "todayPreGameWithModel": len(today_pregame_model),
            "todayPreGameWithPrice": len(today_pregame_with_price),
            "todayPreGameNoPrice": len(today_pregame_no_price),
            "todayStrongModelNoPrice": len(model_strong_no_price),
            "sportsbookOddsFound": diagnostics.get("sportsbookOddsFound"),
            "rowsWithRealPrice": diagnostics.get("rowsWithRealPrice"),
            "polymarketCleanMoneylineFound": diagnostics.get("polymarketCleanMoneylineFound"),
        },
        "pricedTodayTop": priced_today[:20],
        "possibleValueNoPriceTop": possible_value_no_price[:20],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 85 MARKET PRICE MATCHING AUDIT",
        "=" * 56,
        f"Generated UTC: {audit['generatedAt']}",
        "",
        "Counts:",
    ]

    for k, v in audit["counts"].items():
        lines.append(f"- {k}: {v}")

    lines += [
        "",
        "Priced today top:",
    ]

    if priced_today:
        for r in priced_today[:10]:
            lines.append(
                f"- {r.get('awayTeam')} @ {r.get('homeTeam')} | Pick={r.get('selectedSide')} | "
                f"Market={r.get('marketProbability')} | Model={r.get('calibratedProbability')} | "
                f"Edge={r.get('edge')} | Source={r.get('priceSourceUsed')}"
            )
    else:
        lines.append("- none")

    lines += [
        "",
        "Strong model but no price:",
    ]

    if possible_value_no_price:
        for r in possible_value_no_price[:12]:
            lines.append(
                f"- {r.get('awayTeam')} @ {r.get('homeTeam')} | Pick={r.get('selectedSide')} | "
                f"Model={r.get('calibratedProbability')} | Score={r.get('modelScore')} | Quality={r.get('dataQuality')} | "
                f"Reason={r.get('mainReason')}"
            )
    else:
        lines.append("- none")

    lines += [
        "",
        f"JSON: {JSON_OUT}",
        "",
        "Rule: audit only. No Telegram send. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
