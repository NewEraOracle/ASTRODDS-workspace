# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

REPORT = BASE / "reports" / "96_over_under_daily_audit_report.txt"
JSON_OUT = ROOT / ".astrodds" / "ASTRODDS-over-under-daily-audit-latest.json"

ODDS_URL = "http://localhost:3000/api/astrodds/odds/status?sportKey=baseball_mlb&fetch=true"
ET = ZoneInfo("America/Toronto")

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def et_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET)
    except Exception:
        return None

def is_today(value):
    dt = et_dt(value)
    if not dt:
        return False
    return dt.date().isoformat() == datetime.now(ET).date().isoformat()

def is_pregame(value):
    dt = et_dt(value)
    if not dt:
        return False
    return dt > datetime.now(ET)

def american_label(value):
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except Exception:
        return "-"

def clean_price_ok(row):
    price = fnum(row.get("impliedProbability"))
    american = fnum(row.get("priceAmerican"))

    if price is None:
        return False

    # Avoid extreme juice. This keeps it beginner-safe.
    if american is not None and (american < -190 or american > 180):
        return False

    return 0.35 <= price <= 0.67

def pair_totals(rows):
    groups = {}
    for r in rows:
        key = "|".join([
            str(r.get("gameId") or ""),
            str(r.get("commenceTime") or ""),
            str(r.get("awayTeam") or ""),
            str(r.get("homeTeam") or ""),
            str(r.get("line") or ""),
        ])
        groups.setdefault(key, []).append(r)

    paired = []
    for key, items in groups.items():
        over = next((x for x in items if str(x.get("side")).lower() == "over"), None)
        under = next((x for x in items if str(x.get("side")).lower() == "under"), None)
        if over and under:
            paired.append((over, under))

    return paired

def ou_signal(over, under):
    line = fnum(over.get("line"))
    over_prob = fnum(over.get("impliedProbability"))
    under_prob = fnum(under.get("impliedProbability"))
    over_american = fnum(over.get("priceAmerican"))
    under_american = fnum(under.get("priceAmerican"))

    if line is None or over_prob is None or under_prob is None:
        return None

    if not clean_price_ok(over) or not clean_price_ok(under):
        return None

    # Audit-only heuristic:
    # We are NOT claiming a true predictive model yet.
    # This finds market-pressure candidates for review.
    diff = over_prob - under_prob

    pick = None
    confidence = "watch"
    stake = "No stake"

    if diff >= 0.08:
        pick = "Over"
    elif diff <= -0.08:
        pick = "Under"

    if not pick:
        return None

    # Avoid weird very high/low totals until model is added.
    if line < 5.5 or line > 12.5:
        confidence = "watch"
        stake = "No stake"
        reason = "Extreme total line. Review only."
    elif abs(diff) >= 0.12:
        confidence = "O/U_LEAN"
        stake = "1-2% max / paper"
        reason = "Same-day sportsbook total market pressure. Needs model confirmation."
    else:
        confidence = "O/U_WATCH"
        stake = "No stake"
        reason = "Small O/U market lean. Watch only."

    row = over if pick == "Over" else under

    return {
        "category": confidence,
        "stake": stake,
        "date": row.get("commenceTime"),
        "game": row.get("game"),
        "homeTeam": row.get("homeTeam"),
        "awayTeam": row.get("awayTeam"),
        "pick": f"{pick} {line}",
        "line": line,
        "overAmerican": int(over_american) if over_american is not None else None,
        "underAmerican": int(under_american) if under_american is not None else None,
        "overImpliedProbability": over_prob,
        "underImpliedProbability": under_prob,
        "marketPressureDiff": round(diff, 4),
        "reason": reason,
    }

def main():
    data = fetch_json(ODDS_URL)
    odds = data.get("odds") or []

    total_rows = [
        r for r in odds
        if str(r.get("marketType") or "").lower() == "total"
        and str(r.get("side") or "").lower() in ["over", "under"]
        and r.get("line") is not None
    ]

    today_total_rows = [r for r in total_rows if is_today(r.get("commenceTime"))]
    pregame_total_rows = [r for r in today_total_rows if is_pregame(r.get("commenceTime"))]

    pairs = pair_totals(pregame_total_rows)
    signals = []
    for over, under in pairs:
        sig = ou_signal(over, under)
        if sig:
            signals.append(sig)

    signals.sort(key=lambda x: abs(x.get("marketPressureDiff") or 0), reverse=True)

    output = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "audit_only",
        "rules": {
            "market": "Over/Under full-game totals only",
            "excluded": ["moneyline handled elsewhere", "runline/spread", "props", "futures", "tomorrow games"],
            "publicSend": False,
            "note": "This is market-pressure audit only. True O/U picks require model total confirmation.",
        },
        "counts": {
            "oddsRows": len(odds),
            "totalRows": len(total_rows),
            "todayTotalRows": len(today_total_rows),
            "pregameTotalRows": len(pregame_total_rows),
            "pairedPregameTotals": len(pairs),
            "ouLeanCandidates": len([s for s in signals if s["category"] == "O/U_LEAN"]),
            "ouWatchCandidates": len([s for s in signals if s["category"] == "O/U_WATCH"]),
        },
        "signals": signals[:12],
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "ASTRODDS 96 OVER/UNDER DAILY AUDIT",
        "=" * 56,
        f"Generated UTC: {output['generatedAt']}",
        "",
        "Rules:",
        "- Over/Under full-game totals only.",
        "- No runline/spread.",
        "- No props.",
        "- Same-day only.",
        "- Audit only. No Telegram send.",
        "",
        "Counts:",
    ]

    for k, v in output["counts"].items():
        lines.append(f"- {k}: {v}")

    lines += ["", "O/U candidates:"]

    if not signals:
        lines.append("- none")
    else:
        for s in signals[:12]:
            lines.append(
                f"- {s['category']} | {s['game']} | Pick={s['pick']} | "
                f"Over={american_label(s.get('overAmerican'))} | Under={american_label(s.get('underAmerican'))} | "
                f"Pressure={s['marketPressureDiff']} | Stake={s['stake']} | Reason={s['reason']}"
            )

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
