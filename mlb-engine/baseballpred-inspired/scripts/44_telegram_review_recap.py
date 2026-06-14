from pathlib import Path
import json
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

ENV = ROOT / ".env.local"
INPUT = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-review-recap-ledger.json"
REPORT = BASE / "reports" / "44_telegram_review_recap_report.txt"


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


def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def mask(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def make_content_key(rows):
    compact = []

    for row in rows:
        compact.append({
            "game": row.get("game"),
            "pick": row.get("pick"),
            "decision": row.get("thresholdContextDecision"),
            "probability": row.get("thresholdCalibratedProbability"),
            "edge": row.get("edgePct"),
            "flags": row.get("thresholdContextFlags"),
        })

    raw = json.dumps(compact, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_message(rows):
    lines = []

    lines.append("🟡 ASTRODDS REVIEW BOARD")
    lines.append("REVIEW ONLY — NOT OFFICIAL BUY")
    lines.append("")
    lines.append("Strong full-slate candidates detected, but context is not clean enough for ENGINE_BUY.")
    lines.append("")

    for row in rows[:5]:
        probability = round(fnum(row.get("thresholdCalibratedProbability")) * 100, 2)
        edge = row.get("edgePct")
        flags = row.get("thresholdContextFlags") or "none"

        lines.append(f"• {row.get('game')}")
        lines.append(f"  Pick: {row.get('pick')}")
        lines.append(f"  Probability: {probability}%")
        lines.append(f"  Edge: {edge}%")
        lines.append(f"  Decision: {row.get('thresholdContextDecision')}")
        lines.append(f"  Flags: {flags}")
        lines.append("")

    lines.append("Paper/manual only. No real-money automation.")

    return "\n".join(lines)


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    request = urllib.request.Request(url, data=data, method="POST")

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    token = env_value("TELEGRAM_BOT_TOKEN")
    chat_id = (
        env_value("TELEGRAM_DEV_CHAT_ID")
        or env_value("TELEGRAM_CHAT_ID")
        or env_value("TELEGRAM_SIGNALS_CHAT_ID")
    )

    rows = read_json(INPUT, [])
    ledger = read_json(LEDGER, [])

    if not isinstance(rows, list):
        rows = []

    if not isinstance(ledger, list):
        ledger = []

    candidates = []

    for row in rows:
        decision = str(row.get("thresholdContextDecision") or "")

        if decision in ["FULL_CONTEXT_A_REVIEW", "FULL_CONTEXT_A_REVIEW_CLEAN"]:
            candidates.append(row)

    candidates = sorted(
        candidates,
        key=lambda row: (
            fnum(row.get("thresholdCalibratedProbability")),
            fnum(row.get("edgePct")),
        ),
        reverse=True,
    )

    recap_key = "review_recap|" + make_content_key(candidates)
    sent_keys = set(item.get("recapKey") for item in ledger)

    status = "OK"
    sent = 0
    skipped_duplicate = 0
    errors = []

    if not token or not chat_id:
        status = "MISSING_ENV"
    elif not candidates:
        status = "NO_CANDIDATES"
    elif recap_key in sent_keys:
        status = "DUPLICATE"
        skipped_duplicate = 1
    else:
        try:
            result = send_telegram(token, chat_id, build_message(candidates))

            ledger.append({
                "sentAt": datetime.utcnow().isoformat() + "Z",
                "recapKey": recap_key,
                "candidateCount": len(candidates),
                "telegramOk": result.get("ok"),
                "paperOnly": True,
            })

            write_json(LEDGER, ledger)
            sent = 1

        except Exception as error:
            status = "ERROR"
            errors.append(str(error))

    lines = []

    lines.append("ASTRODDS 44 TELEGRAM REVIEW RECAP REPORT")
    lines.append("=" * 52)
    lines.append(f"Status: {status}")
    lines.append(f"Token: {mask(token)}")
    lines.append(f"Chat: {mask(chat_id)}")
    lines.append("")
    lines.append(f"Input rows: {len(rows)}")
    lines.append(f"Review candidates: {len(candidates)}")
    lines.append(f"Sent this run: {sent}")
    lines.append(f"Skipped duplicate: {skipped_duplicate}")
    lines.append(f"Ledger rows: {len(ledger)}")
    lines.append("")
    lines.append("Candidates:")

    for row in candidates[:5]:
        probability = round(fnum(row.get("thresholdCalibratedProbability")) * 100, 2)

        lines.append(
            f"- {row.get('game')} | Pick: {row.get('pick')} | "
            f"Prob={probability}% | Edge={row.get('edgePct')}% | "
            f"Flags={row.get('thresholdContextFlags')}"
        )

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    lines.append("")
    lines.append("Rule: review recap only. Not official buys. Paper/manual only.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")


if __name__ == "__main__":
    main()