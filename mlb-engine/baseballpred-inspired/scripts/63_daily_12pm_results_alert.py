from pathlib import Path
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENV = ROOT / ".env.local"
DAILY = ROOT / ".astrodds" / "ASTRODDS-daily-performance-latest.json"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
DUP_LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-daily-results-ledger.json"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-daily-results-12pm-latest.json"
REPORT = BASE / "reports" / "63_daily_12pm_results_alert_report.txt"

TZ = ZoneInfo("America/Toronto")

def load_env(path):
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def mask(value):
    if not value:
        return "missing"
    value = str(value)
    return value[:4] + "***" + value[-4:] if len(value) > 8 else "***"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def fnum(v):
    try:
        if v is None or str(v).strip() == "":
            return 0.0
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0

def get_first(obj, keys, default=None):
    if not isinstance(obj, dict):
        return default
    for k in keys:
        if k in obj and obj.get(k) is not None:
            return obj.get(k)
    return default

def parse_dt(value):
    if not value:
        return None
    try:
        s = str(value)
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def row_montreal_date(row):
    dt = parse_dt(row.get("date") or row.get("commenceTime") or row.get("gameTime") or row.get("resolvedAt"))
    if not dt:
        return None
    return dt.astimezone(TZ).date().isoformat()

def summarize_from_ledger_for_day(day):
    ledger = read_json(LEDGER, [])
    if not isinstance(ledger, list):
        ledger = []
    rows = [r for r in ledger if isinstance(r, dict) and row_montreal_date(r) == day]
    wins = sum(1 for r in rows if str(r.get("result", "")).lower() == "win")
    losses = sum(1 for r in rows if str(r.get("result", "")).lower() == "loss")
    pending = sum(1 for r in rows if str(r.get("result", "pending")).lower() not in ["win", "loss", "push", "void"])
    resolved = wins + losses
    win_rate = round((wins / resolved) * 100, 1) if resolved else None
    units = round(sum(fnum(r.get("paperProfitUnits")) for r in rows), 3)
    official = sum(1 for r in rows if str(r.get("finalEngineDecision", "")).upper() == "ENGINE_BUY")
    return {
        "signals": len(rows),
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "resolved": resolved,
        "winRatePct": win_rate,
        "paperUnits": units,
        "officialBuys": official,
        "source": "ledger_day_filter",
    }

def summarize_daily_performance(day):
    daily = read_json(DAILY, {})
    if not isinstance(daily, dict):
        return summarize_from_ledger_for_day(day)

    signals = int(get_first(daily, ["totalSignals", "signals", "signalCount"], 0) or 0)
    wins = int(get_first(daily, ["wins", "winCount"], 0) or 0)
    losses = int(get_first(daily, ["losses", "lossCount"], 0) or 0)
    pending = int(get_first(daily, ["pending", "pendingCount"], 0) or 0)
    resolved = int(get_first(daily, ["resolved", "resolvedSignals"], wins + losses) or 0)
    official = int(get_first(daily, ["engineBuy", "engineBuyCount", "officialBuys"], 0) or 0)

    wr = get_first(daily, ["winRatePct", "winRate", "accuracy"], None)
    if wr is None:
        win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) else None
    else:
        win_rate = fnum(wr)
        if win_rate <= 1:
            win_rate *= 100
        win_rate = round(win_rate, 1)

    units = round(fnum(get_first(daily, ["paperUnits", "paperProfitUnits", "profitUnits"], 0)), 3)

    # If daily performance has real rows, trust it. It is the final resolved daily report.
    if signals > 0 or wins > 0 or losses > 0:
        return {
            "signals": signals,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "resolved": resolved,
            "winRatePct": win_rate,
            "paperUnits": units,
            "officialBuys": official,
            "source": "daily_performance_latest",
        }

    return summarize_from_ledger_for_day(day)

def format_units(v):
    return f"{fnum(v):.3f}u"

def format_wr(v):
    return "N/A" if v is None else f"{float(v):.1f}%"

def telegram_send(token, chat_id, text):
    if not token or not chat_id:
        return False, "missing token/chat"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return True, resp.read().decode("utf-8", errors="ignore")[:500]

def build_message(day, s):
    return "\n".join([
        "ASTRODDS DAILY RESULTS",
        f"Date: {day}",
        "",
        f"Signals: {s['signals']}",
        f"Wins: {s['wins']}",
        f"Losses: {s['losses']}",
        f"Pending: {s['pending']}",
        f"Win rate: {format_wr(s['winRatePct'])}",
        f"Paper units: {format_units(s['paperUnits'])}",
        f"Official buys: {s['officialBuys']}",
        "",
        "Paper/manual only. No real-money automation.",
    ])

def remove_duplicate_key(path, key):
    data = read_json(path, {})
    changed = False
    if isinstance(data, dict) and key in data:
        data.pop(key, None)
        changed = True
    elif isinstance(data, list) and key in data:
        data = [x for x in data if x != key]
        changed = True
    if changed:
        write_json(path, data)

def main():
    generated = datetime.now(timezone.utc).isoformat()
    env = load_env(ENV)
    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("ASTRODDS_TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_RESULTS_CHAT_ID") or env.get("TELEGRAM_CHAT_ID") or env.get("ASTRODDS_TELEGRAM_CHAT_ID")

    day = datetime.now(TZ).date().isoformat()
    key = f"daily-results|{day}"

    dedupe = read_json(DUP_LEDGER, {})
    duplicate = (key in dedupe) if isinstance(dedupe, dict) else (key in dedupe if isinstance(dedupe, list) else False)

    summary = summarize_daily_performance(day)
    message = build_message(day, summary)

    sent = False
    err = ""
    if duplicate:
        status = "DUPLICATE"
    else:
        try:
            sent, _ = telegram_send(token, chat_id, message)
            status = "OK" if sent else "ERROR"
            if sent:
                if isinstance(dedupe, dict):
                    dedupe[key] = {"sentAt": generated, "summary": summary}
                else:
                    dedupe = list(dedupe) if isinstance(dedupe, list) else []
                    dedupe.append(key)
                write_json(DUP_LEDGER, dedupe)
        except Exception as exc:
            status = "ERROR"
            err = str(exc)

    out = {
        "generatedAt": generated,
        "status": status,
        "sent": sent,
        "duplicate": duplicate,
        "token": mask(token),
        "chat": mask(chat_id),
        "montrealDate": day,
        "summary": summary,
        "message": message,
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(OUT_JSON, out)

    lines = [
        "ASTRODDS 63 DAILY 12PM RESULTS ALERT REPORT",
        "=" * 56,
        f"Generated: {generated}",
        "",
        f"Status: {status}",
    ]
    if err:
        lines.append(f"Send error: {err}")
    lines += [
        f"Source: {summary['source']}",
        f"Sent this run: {1 if sent else 0}",
        f"Skipped duplicate: {1 if duplicate else 0}",
        "",
        f"Signals: {summary['signals']}",
        f"Wins: {summary['wins']}",
        f"Losses: {summary['losses']}",
        f"Pending: {summary['pending']}",
        f"Win rate: {format_wr(summary['winRatePct'])}",
        f"Paper units: {format_units(summary['paperUnits'])}",
        f"Official buys: {summary['officialBuys']}",
        "",
        "Telegram message:",
        message,
        "",
        f"JSON: {OUT_JSON}",
        "Rule: daily results only. No odds scan. No betting automation.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
