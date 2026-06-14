from pathlib import Path
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENV = ROOT / ".env.local"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
DUP_LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-daily-results-ledger.json"

REPORT = BASE / "reports" / "63_daily_11pm_results_alert_report.txt"
OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-daily-results-11pm-latest.json"

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
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]

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

def parse_dt(value):
    if not value:
        return None
    s = str(value)
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def row_montreal_date(row):
    # Prefer game date for daily game results.
    dt = parse_dt(row.get("date") or row.get("commenceTime") or row.get("gameTime"))
    if not dt:
        dt = parse_dt(row.get("resolvedAt") or row.get("ledgerAddedAt"))
    if not dt:
        return None
    return dt.astimezone(TZ).date().isoformat()

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

def result_key(row):
    return str(row.get("result") or "pending").lower()

def category(row):
    decision = str(row.get("finalEngineDecision") or row.get("decision") or "").upper()
    grade = str(row.get("finalGrade") or row.get("grade") or "").upper()
    if decision == "ENGINE_BUY":
        return "OFFICIAL_BUY"
    if decision == "MANUAL_REVIEW" and grade == "A":
        return "A_REVIEW"
    if decision == "MANUAL_REVIEW" and grade == "B":
        return "B_REVIEW"
    if grade == "WATCH" or decision == "WATCH":
        return "WATCH"
    return decision or grade or "UNKNOWN"

def summarize(rows):
    wins = [r for r in rows if result_key(r) == "win"]
    losses = [r for r in rows if result_key(r) == "loss"]
    pushes = [r for r in rows if result_key(r) in ["push", "void"]]
    pending = [r for r in rows if result_key(r) not in ["win", "loss", "push", "void"]]
    resolved = len(wins) + len(losses)
    win_rate = round((len(wins) / resolved) * 100, 2) if resolved else None
    units = round(sum(fnum(r.get("paperProfitUnits")) for r in rows), 3)

    by_cat = {}
    for r in rows:
        c = category(r)
        if c not in by_cat:
            by_cat[c] = {"signals": 0, "wins": 0, "losses": 0, "pending": 0, "units": 0.0}
        by_cat[c]["signals"] += 1
        by_cat[c]["units"] += fnum(r.get("paperProfitUnits"))
        res = result_key(r)
        if res == "win":
            by_cat[c]["wins"] += 1
        elif res == "loss":
            by_cat[c]["losses"] += 1
        elif res not in ["push", "void"]:
            by_cat[c]["pending"] += 1

    for c in by_cat.values():
        res = c["wins"] + c["losses"]
        c["winRatePct"] = round((c["wins"] / res) * 100, 2) if res else None
        c["units"] = round(c["units"], 3)

    return {
        "signals": len(rows),
        "resolved": resolved,
        "wins": len(wins),
        "losses": len(losses),
        "pushVoid": len(pushes),
        "pending": len(pending),
        "winRatePct": win_rate,
        "paperUnits": units,
        "engineBuy": sum(1 for r in rows if str(r.get("finalEngineDecision") or "").upper() == "ENGINE_BUY"),
        "byCategory": by_cat,
    }

def format_units(v):
    if v is None:
        return "0u"
    return f"{round(float(v), 3)}u"

def build_message(day, summary):
    wr = "N/A" if summary["winRatePct"] is None else f"{summary['winRatePct']}%"
    lines = []
    lines.append(f"ðŸ“Š ASTRODDS DAILY RESULTS â€” {day}")
    lines.append("")
    lines.append(f"Signals: {summary['signals']}")
    lines.append(f"Wins: {summary['wins']} | Losses: {summary['losses']} | Pending: {summary['pending']}")
    lines.append(f"Win rate: {wr}")
    lines.append(f"Paper units: {format_units(summary['paperUnits'])}")
    lines.append(f"Official buys: {summary['engineBuy']}")
    lines.append("")
    if summary["byCategory"]:
        lines.append("Breakdown:")
        for name in sorted(summary["byCategory"].keys()):
            c = summary["byCategory"][name]
            cwr = "N/A" if c["winRatePct"] is None else f"{c['winRatePct']}%"
            lines.append(f"- {name}: {c['wins']}-{c['losses']} | {cwr} | {format_units(c['units'])}")
        lines.append("")
    lines.append("Paper/manual tracking only. No real-money automation.")
    return "\n".join(lines)

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
        body = resp.read().decode("utf-8", errors="ignore")
    return True, body[:500]

def main():
    generated = datetime.now(timezone.utc).isoformat()
    env = load_env(ENV)
    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("ASTRODDS_TELEGRAM_BOT_TOKEN")
    chat_id = (
        env.get("TELEGRAM_RESULTS_CHAT_ID")
        or env.get("TELEGRAM_CHAT_ID")
        or env.get("ASTRODDS_TELEGRAM_CHAT_ID")
    )

    today = datetime.now(TZ).date().isoformat()
    ledger = read_json(LEDGER, [])
    if not isinstance(ledger, list):
        ledger = []

    today_rows = [r for r in ledger if row_montreal_date(r) == today]
    summary = summarize(today_rows)
    message = build_message(today, summary)

    dup = read_json(DUP_LEDGER, {})
    if not isinstance(dup, dict):
        dup = {}

    key = f"daily-results|{today}"
    duplicate = key in dup

    sent = False
    send_error = ""
    if duplicate:
        status = "DUPLICATE"
    else:
        try:
            sent, send_response = telegram_send(token, chat_id, message)
            status = "OK" if sent else "ERROR"
            if sent:
                dup[key] = {"sentAt": generated, "day": today, "summary": summary}
                write_json(DUP_LEDGER, dup)
            else:
                send_error = send_response
        except Exception as exc:
            status = "ERROR"
            send_error = str(exc)

    output = {
        "generatedAt": generated,
        "montrealDate": today,
        "status": status,
        "sent": sent,
        "duplicate": duplicate,
        "token": mask(token),
        "chat": mask(chat_id),
        "summary": summary,
        "rows": today_rows,
        "message": message,
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(OUT_JSON, output)

    lines = []
    lines.append("ASTRODDS 63 DAILY 11PM RESULTS ALERT REPORT")
    lines.append("=" * 56)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {status}")
    if send_error:
        lines.append(f"Send error: {send_error}")
    lines.append(f"Montreal date: {today}")
    lines.append(f"Token: {mask(token)}")
    lines.append(f"Chat: {mask(chat_id)}")
    lines.append(f"Sent this run: {1 if sent else 0}")
    lines.append(f"Skipped duplicate: {1 if duplicate else 0}")
    lines.append("")
    lines.append(f"Signals: {summary['signals']}")
    lines.append(f"Resolved: {summary['resolved']}")
    lines.append(f"Wins: {summary['wins']}")
    lines.append(f"Losses: {summary['losses']}")
    lines.append(f"Pending: {summary['pending']}")
    lines.append(f"Win rate: {summary['winRatePct']}%")
    lines.append(f"Paper units: {summary['paperUnits']}u")
    lines.append(f"ENGINE_BUY: {summary['engineBuy']}")
    lines.append("")
    lines.append("Telegram message:")
    lines.append(message)
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append(f"Dedup ledger: {DUP_LEDGER}")
    lines.append("")
    lines.append("Rule: daily results only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

