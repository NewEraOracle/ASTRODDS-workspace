# -*- coding: utf-8 -*-
"""
ASTRODDS 120 - Daily 12PM Verified Results Telegram

Purpose:
- Run the resolver 119 first.
- Read Official Telegram A+ Results.
- Read O/U Paper Test Results.
- Build a daily 12PM proof update message.
- Send to Telegram only when explicitly enabled.

Safety:
- Does not create picks.
- Does not change official signal logic.
- Telegram send is disabled unless ASTRODDS_SEND_TELEGRAM_RESULTS=true.
- If token/chat_id missing, it writes a report and exits cleanly.
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

RESOLVER_119 = SCRIPT_DIR / "119_resolve_verified_and_ou_results.py"

OFFICIAL_JSON = ROOT / "public" / "astrodds-verified-telegram-results.json"
OU_JSON = ROOT / "public" / "astrodds-ou-paper-test-results.json"

OFFICIAL_HTML = ROOT / "public" / "astrodds-verified-telegram-results.html"
OU_HTML = ROOT / "public" / "astrodds-ou-paper-test-results.html"

REPORT = BASE / "reports" / "120_daily_12pm_verified_results_telegram_report.txt"

ET = ZoneInfo("America/Toronto")

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def yn(value):
    return str(value or "").strip().lower() in ["1", "true", "yes", "y", "on"]

def get_env(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None

def public_link(path_name):
    """
    If ASTRODDS_PUBLIC_BASE_URL is set, create a public URL.
    Example:
      ASTRODDS_PUBLIC_BASE_URL=https://astrodds.com
      -> https://astrodds.com/astrodds-verified-telegram-results.html
    Otherwise return local path label.
    """
    base_url = os.getenv("ASTRODDS_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}/{path_name}"
    return f"local: public/{path_name}"

def run_resolver():
    if not RESOLVER_119.exists():
        return 0, "resolver_missing"

    proc = subprocess.run(
        [sys.executable, str(RESOLVER_119)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    detail = (proc.stdout or "").strip()
    if proc.stderr:
        detail += "\nSTDERR:\n" + proc.stderr.strip()

    return proc.returncode, detail[-4000:]

def build_message():
    official = read_json(OFFICIAL_JSON, {"summary": {}, "signals": []})
    ou = read_json(OU_JSON, {"summary": {}, "signals": []})

    osum = official.get("summary") or {}
    ousum = ou.get("summary") or {}

    official_record = osum.get("record", "0-0")
    official_wr = osum.get("winRateLabel", "N/A")
    official_verified = len(official.get("signals") or [])
    official_pending = osum.get("pending", 0)

    ou_record = ousum.get("record", "0-0")
    ou_wr = ousum.get("winRateLabel", "N/A")
    ou_signals = ousum.get("ouPaperSignals", len(ou.get("signals") or []))
    ou_pending = ousum.get("pending", 0)

    official_link = public_link("astrodds-verified-telegram-results.html")
    ou_link = public_link("astrodds-ou-paper-test-results.html")

    lines = [
        "📊 ASTRODDS DAILY RESULTS UPDATE",
        "",
        "✅ Official Telegram A+ Results",
        f"Record: {official_record}",
        f"Win Rate: {official_wr}",
        f"Verified Signals: {official_verified}",
        f"Pending: {official_pending}",
        "",
        "🧪 Over/Under Paper Test",
        f"Record: {ou_record}",
        f"Win Rate: {ou_wr}",
        f"Test Signals: {ou_signals}",
        f"Pending: {ou_pending}",
        "",
        "📄 Updated Documents",
        f"Official: {official_link}",
        f"O/U Test: {ou_link}",
        "",
        "Rule: official win rate counts only verified Telegram A+ signals.",
        f"Updated: {datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')}",
    ]

    return "\n".join(lines)

def send_telegram(message):
    enabled = yn(os.getenv("ASTRODDS_SEND_TELEGRAM_RESULTS"))
    token = get_env("ASTRODDS_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    chat_id = get_env("ASTRODDS_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")

    if not enabled:
        return False, "send_disabled_set_ASTRODDS_SEND_TELEGRAM_RESULTS_true"
    if not token or not chat_id:
        return False, "missing_telegram_token_or_chat_id"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        body = r.read().decode("utf-8")

    return True, body[:1000]

def main():
    generated = datetime.now(ET).isoformat()

    resolver_code, resolver_detail = run_resolver()
    message = build_message()

    try:
        sent, send_detail = send_telegram(message)
    except Exception as e:
        sent = False
        send_detail = f"telegram_error:{type(e).__name__}:{e}"

    lines = [
        "ASTRODDS 120 DAILY 12PM VERIFIED RESULTS TELEGRAM",
        "=" * 70,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Runs 119 resolver first.",
        "- Reads official A+ results and O/U paper-test results.",
        "- Sends Telegram only if ASTRODDS_SEND_TELEGRAM_RESULTS=true.",
        "- Does not create picks.",
        "",
        f"Resolver exit code: {resolver_code}",
        f"Telegram sent: {sent}",
        f"Telegram detail: {send_detail}",
        "",
        "Message preview:",
        "-" * 40,
        message,
        "-" * 40,
        "",
        "Resolver detail tail:",
        resolver_detail or "-",
        "",
        f"Official HTML: {OFFICIAL_HTML}",
        f"O/U HTML: {OU_HTML}",
        "",
        "Rule: reporting only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
