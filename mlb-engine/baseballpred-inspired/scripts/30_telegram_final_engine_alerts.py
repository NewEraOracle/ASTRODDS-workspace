from pathlib import Path
import json
import urllib.parse
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

ENV = ROOT / ".env.local"
SIGNALS = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-alert-ledger.json"
REPORT = BASE / "reports" / "30_telegram_final_engine_alerts_report.txt"

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
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def mask(v):
    if not v:
        return ""
    return v[:4] + "***" + v[-4:] if len(v) > 8 else "***"

def key(row):
    return "|".join([
        str(row.get("date", "")),
        str(row.get("game", "")),
        str(row.get("pick", "")),
        str(row.get("finalEngineDecision", "")),
        str(row.get("finalGrade", "")),
    ])

def pct(x):
    try:
        v = float(str(x).replace(",", "."))
        return f"{round(v * 100, 2)}%" if abs(v) <= 1 else f"{round(v, 2)}%"
    except Exception:
        return "-"

def message(row):
    return (
        "ASTRODDS ENGINE BUY\n\n"
        f"Game: {row.get('game')}\n"
        f"Pick: {row.get('pick')}\n"
        f"Grade: {row.get('finalGrade')}\n"
        f"Decision: {row.get('finalEngineDecision')}\n\n"
        f"Market: {pct(row.get('marketProbability'))}\n"
        f"Calibrated: {pct(row.get('calibratedProbabilityV2'))}\n"
        f"Cal Edge: {row.get('calibratedEdgePct')}%\n\n"
        f"Reason: {row.get('finalReason')}\n"
        f"Game time: {row.get('date')}\n\n"
        "Paper/manual only. No real-money automation."
    )

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
    token = env_value("TELEGRAM_BOT_TOKEN")
    chat_id = env_value("TELEGRAM_SIGNALS_CHAT_ID") or env_value("TELEGRAM_CHAT_ID")

    signals = read_json(SIGNALS)
    ledger = read_json(LEDGER)
    sent_keys = set(x.get("alertKey") for x in ledger)

    eligible = [
        r for r in signals
        if r.get("finalEngineDecision") == "ENGINE_BUY"
        and r.get("finalGrade") in ["A+", "A"]
    ]

    sent = 0
    skipped = 0
    errors = []

    if not token or not chat_id:
        lines = [
            "ASTRODDS 30 TELEGRAM FINAL ENGINE ALERTS REPORT",
            "=" * 56,
            "Status: MISSING_ENV",
            "Need TELEGRAM_BOT_TOKEN and TELEGRAM_SIGNALS_CHAT_ID or TELEGRAM_CHAT_ID in .env.local",
        ]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    for row in eligible:
        alert_key = key(row)
        if alert_key in sent_keys:
            skipped += 1
            continue

        try:
            res = send(token, chat_id, message(row))
            ledger.append({
                "sentAt": datetime.utcnow().isoformat() + "Z",
                "alertKey": alert_key,
                "game": row.get("game"),
                "pick": row.get("pick"),
                "decision": row.get("finalEngineDecision"),
                "grade": row.get("finalGrade"),
                "telegramOk": res.get("ok"),
                "paperOnly": True,
            })
            sent += 1
        except Exception as e:
            errors.append(f"{row.get('game')} | {row.get('pick')}: {e}")

    write_json(LEDGER, ledger)

    lines = [
        "ASTRODDS 30 TELEGRAM FINAL ENGINE ALERTS REPORT",
        "=" * 56,
        "Status: OK",
        f"Token: {mask(token)}",
        f"Chat: {mask(chat_id)}",
        "",
        f"Input signals: {len(signals)}",
        f"Eligible ENGINE_BUY alerts: {len(eligible)}",
        f"Sent this run: {sent}",
        f"Skipped duplicates: {skipped}",
        f"Ledger rows: {len(ledger)}",
        "",
        "Rule: send only ENGINE_BUY with grade A+ or A.",
        "Paper/manual only. No real-money automation.",
    ]

    if eligible:
        lines.append("")
        lines.append("Eligible alerts:")
        for row in eligible:
            lines.append(f"- {row.get('game')} | Pick: {row.get('pick')} | Grade: {row.get('finalGrade')} | Edge: {row.get('calibratedEdgePct')}%")

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append(f"Alert ledger: {LEDGER}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
