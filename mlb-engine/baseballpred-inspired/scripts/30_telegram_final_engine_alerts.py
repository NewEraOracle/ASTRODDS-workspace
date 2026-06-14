# -*- coding: utf-8 -*-
from pathlib import Path
import json, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

ENV = ROOT / ".env.local"
SIGNALS = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-alert-ledger.json"
REPORT = BASE / "reports" / "30_telegram_final_engine_alerts_report.txt"

ENTRY_BUFFER = 0.07

def env_value(name):
    if not ENV.exists():
        return None
    for line in ENV.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == name:
            return v.strip().strip('"').strip("'")
    return None

def read_json(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def num(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def prob(x):
    x = num(x)
    if x is None:
        return None
    if x > 1:
        x = x / 100
    if x < 0 or x > 1:
        return None
    return x

def pct(x):
    x = num(x)
    if x is None:
        return "-"
    if abs(x) <= 1:
        x *= 100
    return f"{x:.2f}%"

def price(x):
    x = prob(x)
    return "-" if x is None else f"${x:.2f}"

def market(row):
    return prob(row.get("marketProbability") or row.get("currentMarketProbability") or row.get("marketPrice"))

def calibrated_prob(row):
    return prob(row.get("calibratedProbabilityV2") or row.get("calibratedProbability") or row.get("modelProbability"))

def edge(row):
    return num(row.get("calibratedEdgePct") or row.get("edgePct"))

def entry(row):
    p = calibrated_prob(row)
    if p is None:
        return None
    return round(max(0.01, min(0.99, p - ENTRY_BUFFER)), 2)

def dec(row):
    return str(row.get("finalEngineDecision") or row.get("finalDecision") or row.get("decision") or "").upper()

def grade(row):
    return str(row.get("finalGrade") or row.get("grade") or "").upper()

def game(row):
    away = row.get("awayTeam")
    home = row.get("homeTeam")
    if away and home:
        return f"{away} @ {home}"
    return row.get("game") or "-"

def warnings(row):
    c = 0
    p = str(row.get("humanPitcherWarnings") or "").strip().lower()
    b = str(row.get("humanBullpenWarnings") or "").strip().lower()
    if p and p != "none":
        c += 1
    if b and b != "none":
        c += 1
    return c



ASTRODDS_TODAY_TZ = ZoneInfo("America/Toronto")

def et_date_key(value):
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(ASTRODDS_TODAY_TZ).date().isoformat()
    except Exception:
        return None

def is_today_game(row):
    row_key = et_date_key(row.get("date"))
    today_key = datetime.now(ASTRODDS_TODAY_TZ).date().isoformat()
    return bool(row_key and row_key == today_key)
def is_active_game(row):
    detailed = str(row.get("mlbDetailedStatus") or "").strip().lower()
    abstract = str(row.get("mlbAbstractStatus") or "").strip().lower()
    result = str(row.get("result") or "").strip().lower()

    if detailed == "final" or abstract == "final":
        return False

    if result in ["final", "completed", "closed", "settled"]:
        return False

    return True
def is_a_pick(row):
    market_price = market(row)
    entry_max = entry(row)
    row_edge = edge(row)

    return (
        is_active_game(row)
        and is_today_game(row)
        and dec(row) == "ENGINE_BUY"
        and grade(row) in ["A", "A+"]
        and market_price is not None
        and entry_max is not None
        and row_edge is not None
        and row_edge >= 3
        and market_price <= entry_max
    )
def is_value_lean(row):
    market_price = market(row)
    entry_max = entry(row)
    row_edge = edge(row)
    cp = calibrated_prob(row)

    if not is_active_game(row):
        return False

    if not is_today_game(row):
        return False

    if dec(row) == "ENGINE_BUY":
        return False

    if dec(row) in ["WATCH", "NO_BET", "BLOCKED"]:
        return False

    if grade(row) not in ["A", "B", "A+"]:
        return False

    if market_price is None or entry_max is None or row_edge is None or cp is None:
        return False

    return (
        row_edge >= 7
        and cp >= 0.60
        and market_price <= entry_max + 0.02
        and warnings(row) <= 2
    )
def key(row, label):
    return "|".join([
        label,
        str(row.get("date", "")),
        str(row.get("game", "")),
        str(row.get("pick", "")),
        dec(row),
        grade(row),
    ])

def format_a(row, i):
    return "\n".join([
        f"{i}) Pick: {row.get('pick')}",
        f"Game: {game(row)}",
        f"Entry max: {price(entry(row))}",
        f"Market: {price(market(row))}",
        "Stake: 5% bankroll",
        f"Reason: strong value, edge {pct(edge(row))}, price under entry."
    ])

def format_value(row, i):
    w = warnings(row)
    reason = f"good value angle, but {w} context warning(s)." if w else "good value angle, lower confidence than A Pick."
    return "\n".join([
        f"{i}) Pick: {row.get('pick')}",
        f"Game: {game(row)}",
        f"Entry max: {price(entry(row))}",
        f"Market: {price(market(row))}",
        "Stake: 1-2% max / paper",
        f"Reason: {reason}"
    ])

def build_message(a_picks, value_leans):
    parts = []

    if a_picks:
        parts.append("ASTRODDS A PICK")
        parts.extend(format_a(r, i + 1) for i, r in enumerate(a_picks))

    if value_leans:
        if parts:
            parts.append("")
        parts.append("ASTRODDS VALUE LEAN")
        parts.extend(format_value(r, i + 1) for i, r in enumerate(value_leans))

    if not parts:
        return "ASTRODDS: No A Pick today. Waiting for better value."

    parts.append("")
    parts.append("Paper/manual only. No real-money automation.")
    return "\n\n".join(parts)

def send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    dry = "--dry-run" in sys.argv
    token = env_value("TELEGRAM_BOT_TOKEN")
    chat_id = env_value("TELEGRAM_SIGNALS_CHAT_ID") or env_value("TELEGRAM_CHAT_ID")

    rows = read_json(SIGNALS)
    ledger = read_json(LEDGER)
    sent = set(x.get("alertKey") for x in ledger)

    a_all = [r for r in rows if is_a_pick(r)]
    v_all = [r for r in rows if is_value_lean(r)]

    a_new = [r for r in a_all if key(r, "A_PICK") not in sent]
    v_new = [r for r in v_all if key(r, "VALUE_LEAN") not in sent]

    text = build_message(a_new, v_new)

    status = "OK"
    telegram_ok = None
    message_id = None
    error = None

    if dry:
        status = "DRY_RUN_NO_SEND"
    elif not token or not chat_id:
        status = "MISSING_ENV"
        error = "Need TELEGRAM_BOT_TOKEN and TELEGRAM_SIGNALS_CHAT_ID or TELEGRAM_CHAT_ID in .env.local"
    elif not a_new and not v_new:
        status = "NO_NEW_PUBLIC_SIGNALS"
    else:
        try:
            res = send(token, chat_id, text)
            telegram_ok = res.get("ok")
            message_id = res.get("result", {}).get("message_id")
            sent_at = datetime.utcnow().isoformat() + "Z"

            for r in a_new:
                ledger.append({
                    "sentAt": sent_at,
                    "alertKey": key(r, "A_PICK"),
                    "publicCategory": "A_PICK",
                    "game": r.get("game"),
                    "pick": r.get("pick"),
                    "date": r.get("date"),
                    "gameId": r.get("gameId"),
                    "gamePk": r.get("gamePk"),
                    "marketProbability": market(r),
                    "entryMax": entry(r),
                    "calibratedProbability": calibrated_prob(r),
                    "edge": edge(r),
                    "telegramOk": telegram_ok,
                    "telegramMessageId": message_id,
                })

            for r in v_new:
                ledger.append({
                    "sentAt": sent_at,
                    "alertKey": key(r, "VALUE_LEAN"),
                    "publicCategory": "VALUE_LEAN",
                    "game": r.get("game"),
                    "pick": r.get("pick"),
                    "date": r.get("date"),
                    "gameId": r.get("gameId"),
                    "gamePk": r.get("gamePk"),
                    "marketProbability": market(r),
                    "entryMax": entry(r),
                    "calibratedProbability": calibrated_prob(r),
                    "edge": edge(r),
                    "telegramOk": telegram_ok,
                    "telegramMessageId": message_id,
                })

            write_json(LEDGER, ledger)
        except Exception as e:
            status = "SEND_ERROR"
            error = str(e)

    blocked = len(rows) - len(a_all) - len(v_all)

    lines = [
        "ASTRODDS 30 TELEGRAM PUBLIC SIGNALS REPORT",
        "=" * 56,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        f"Status: {status}",
        f"Signals input: {len(rows)}",
        f"a_pick_count: {len(a_all)}",
        f"value_lean_count: {len(v_all)}",
        f"blocked_count: {blocked}",
        f"new_a_pick_count: {len(a_new)}",
        f"new_value_lean_count: {len(v_new)}",
        f"telegramOk: {telegram_ok}",
        f"telegramMessageId: {message_id}",
    ]

    if error:
        lines.append(f"Error: {error}")

    lines += [
        "",
        "Public message preview:",
        "-" * 56,
        text,
        "",
        "Rules:",
        "- Public categories only: A PICK and VALUE LEAN.",
        "- A PICK = 5% bankroll.",
        "- VALUE LEAN = 1-2% max / paper.",
        "- Paper/manual only. No real-money automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()


