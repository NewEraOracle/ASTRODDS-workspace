from pathlib import Path
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENV = ROOT / ".env.local"
INPUT = ROOT / ".astrodds" / "ASTRODDS-full-slate-context-threshold-final-latest.json"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-review-recap-ledger.json"
REPORT = BASE / "reports" / "44_telegram_review_recap_report.txt"

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

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def pct(value):
    n = fnum(value)
    if n is None:
        return "N/A"
    if n <= 1:
        n *= 100
    return f"{round(n, 2)}%"

def get_game(row):
    return row.get("game") or f"{row.get('awayTeam', '')} @ {row.get('homeTeam', '')}".strip()

def is_review_candidate(row):
    decision = str(row.get("thresholdDecision") or row.get("decision") or row.get("finalDecision") or "").upper()
    return "REVIEW" in decision or "FULL_CONTEXT" in decision

def telegram_send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")[:500]

def build_message(rows):
    lines = []
    lines.append("ASTRODDS ADMIN REVIEW BOARD")
    lines.append("ADMIN ONLY - NOT OFFICIAL BUY")
    lines.append("")
    lines.append("Review candidates detected. Do not send to public clients.")
    lines.append("")

    for i, r in enumerate(rows[:5], start=1):
        lines.append(f"{i}) {get_game(r)}")
        lines.append(f"Pick: {r.get('pick')}")
        lines.append(f"Probability: {pct(r.get('calibratedProbabilityV2') or r.get('calibratedProbability') or r.get('probability'))}")
        lines.append(f"Edge: {pct(r.get('calibratedEdgePct') or r.get('edge'))}")
        flags = r.get("contextFlags") or r.get("flags") or r.get("reasons") or "none"
        lines.append(f"Flags: {flags}")
        lines.append("")

    lines.append("Public channel rule: OFFICIAL BUY only.")
    lines.append("Paper/manual only. No real-money automation.")
    return "\n".join(lines)

def main():
    generated = datetime.now(timezone.utc).isoformat()
    env = load_env(ENV)

    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("ASTRODDS_TELEGRAM_BOT_TOKEN")
    review_chat = (
        env.get("TELEGRAM_REVIEW_CHAT_ID")
        or env.get("TELEGRAM_ADMIN_CHAT_ID")
        or env.get("ASTRODDS_REVIEW_CHAT_ID")
        or env.get("ASTRODDS_ADMIN_CHAT_ID")
    )

    data = read_json(INPUT, [])
    if not isinstance(data, list):
        data = []

    candidates = [r for r in data if isinstance(r, dict) and is_review_candidate(r)]
    message = build_message(candidates)

    sent = False
    skipped_reason = ""
    status = "OK"

    # Important: never fallback to public TELEGRAM_CHAT_ID for review boards.
    if not token:
        status = "SKIPPED"
        skipped_reason = "missing_telegram_token"
    elif not review_chat:
        status = "SKIPPED_ADMIN_CHAT_NOT_CONFIGURED"
        skipped_reason = "missing TELEGRAM_REVIEW_CHAT_ID or TELEGRAM_ADMIN_CHAT_ID"
    elif not candidates:
        status = "NO_REVIEW_CANDIDATES"
        skipped_reason = "no candidates"
    else:
        ledger = read_json(LEDGER, {})
        if not isinstance(ledger, dict):
            ledger = {}
        key = "review-admin|" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "|" + str(len(candidates))
        if key in ledger:
            status = "DUPLICATE"
            skipped_reason = "duplicate"
        else:
            telegram_send(token, review_chat, message)
            sent = True
            ledger[key] = {"sentAt": generated, "count": len(candidates)}
            write_json(LEDGER, ledger)

    lines = []
    lines.append("ASTRODDS 44 ADMIN REVIEW RECAP REPORT")
    lines.append("=" * 48)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append(f"Token: {mask(token)}")
    lines.append(f"Review/Admin Chat: {mask(review_chat)}")
    lines.append("Public Chat Fallback: DISABLED")
    lines.append(f"Sent this run: {1 if sent else 0}")
    if skipped_reason:
        lines.append(f"Skipped reason: {skipped_reason}")
    lines.append("")
    lines.append(f"Input rows: {len(data)}")
    lines.append(f"Review candidates: {len(candidates)}")
    lines.append("")
    lines.append("Rule:")
    lines.append("- Review board is admin-only.")
    lines.append("- Public Telegram receives OFFICIAL BUY only.")
    lines.append("- No review/watch/wait messages go to public clients.")
    lines.append("- Paper/manual only. No real-money automation.")
    lines.append("")
    lines.append("Message preview:")
    lines.append(message)
    lines.append("")
    lines.append(f"Saved: {REPORT}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()