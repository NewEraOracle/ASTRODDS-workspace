# -*- coding: utf-8 -*-
"""
ASTRODDS 121 - Send Verified Results Documents to Telegram

Purpose:
- Run 119 resolver first.
- Run 120 message/report logic optional via its public JSON outputs.
- Send actual result files to Telegram as documents:
  1) Official A+ verified results HTML
  2) O/U paper test results HTML
  3) Official A+ verified results JSON
  4) O/U paper test results JSON

Safety:
- Sends only if ASTRODDS_SEND_TELEGRAM_RESULTS=true
- Does not create picks
- Does not modify engine decisions
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

RESOLVER_119 = SCRIPT_DIR / "119_resolve_verified_and_ou_results.py"

OFFICIAL_JSON = ROOT / "public" / "astrodds-verified-telegram-results.json"
OFFICIAL_HTML = ROOT / "public" / "astrodds-verified-telegram-results.html"
OU_JSON = ROOT / "public" / "astrodds-ou-paper-test-results.json"
OU_HTML = ROOT / "public" / "astrodds-ou-paper-test-results.html"

REPORT = BASE / "reports" / "121_send_verified_results_documents_telegram_report.txt"
ET = ZoneInfo("America/Toronto")

def yn(value):
    return str(value or "").strip().lower() in ["1", "true", "yes", "y", "on"]

def get_env(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

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

def build_summary_message():
    official = read_json(OFFICIAL_JSON, {"summary": {}, "signals": []})
    ou = read_json(OU_JSON, {"summary": {}, "signals": []})

    osum = official.get("summary") or {}
    ousum = ou.get("summary") or {}

    return "\n".join([
        "ASTRODDS DAILY RESULTS UPDATE",
        "",
        "Official Telegram A+ Results",
        f"Record: {osum.get('record', '0-0')}",
        f"Win Rate: {osum.get('winRateLabel', 'N/A')}",
        f"Verified Signals: {len(official.get('signals') or [])}",
        f"Pending: {osum.get('pending', 0)}",
        "",
        "Over/Under Paper Test",
        f"Record: {ousum.get('record', '0-0')}",
        f"Win Rate: {ousum.get('winRateLabel', 'N/A')}",
        f"Test Signals: {ousum.get('ouPaperSignals', len(ou.get('signals') or []))}",
        f"Pending: {ousum.get('pending', 0)}",
        "",
        "Documents attached below.",
        "Rule: official win rate counts only verified Telegram A+ signals.",
        f"Updated: {datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')}",
    ])

def telegram_post(token, method, fields, files=None):
    url = f"https://api.telegram.org/bot{token}/{method}"

    if not files:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8")

    boundary = "----ASTRODDS" + uuid.uuid4().hex
    body = bytearray()

    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(str(v).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, file_path in files.items():
        path = Path(file_path)
        filename = path.name
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode())
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))

    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8")

def send_message(token, chat_id, text):
    return telegram_post(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    })

def send_document(token, chat_id, path, caption):
    return telegram_post(token, "sendDocument", {
        "chat_id": chat_id,
        "caption": caption,
    }, files={"document": str(path)})

def main():
    generated = datetime.now(ET).isoformat()
    resolver_code, resolver_detail = run_resolver()

    enabled = yn(os.getenv("ASTRODDS_SEND_TELEGRAM_RESULTS"))
    token = get_env("ASTRODDS_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    chat_id = get_env("ASTRODDS_TELEGRAM_CHAT_ID", "TELEGRAM_SIGNALS_CHAT_ID", "TELEGRAM_CHAT_ID")

    sent_items = []
    errors = []

    message = build_summary_message()

    if not enabled:
        errors.append("send_disabled_set_ASTRODDS_SEND_TELEGRAM_RESULTS_true")
    elif not token or not chat_id:
        errors.append("missing_telegram_token_or_chat_id")
    else:
        try:
            send_message(token, chat_id, message)
            sent_items.append("summary_message")
        except Exception as e:
            errors.append(f"summary_message_error:{type(e).__name__}:{e}")

        docs = [
            (OFFICIAL_HTML, "Official A+ Verified Results HTML"),
            (OU_HTML, "Over/Under Paper Test Results HTML"),
        ]

        for path, caption in docs:
            if not path.exists():
                errors.append(f"missing_file:{path}")
                continue
            try:
                send_document(token, chat_id, path, caption)
                sent_items.append(path.name)
            except Exception as e:
                errors.append(f"send_document_error:{path.name}:{type(e).__name__}:{e}")

    lines = [
        "ASTRODDS 121 SEND VERIFIED RESULTS DOCUMENTS TELEGRAM",
        "=" * 72,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Runs 119 resolver first.",
        "- Sends actual HTML/JSON documents as Telegram files.",
        "- Sends only if ASTRODDS_SEND_TELEGRAM_RESULTS=true.",
        "- Does not create picks.",
        "",
        f"Resolver exit code: {resolver_code}",
        f"Telegram enabled: {enabled}",
        f"Sent items: {len(sent_items)}",
    ]

    for item in sent_items:
        lines.append(f"- sent: {item}")

    if errors:
        lines.append("")
        lines.append("Errors/warnings:")
        for e in errors:
            lines.append(f"- {e}")

    lines += [
        "",
        "Message preview:",
        "-" * 40,
        message,
        "-" * 40,
        "",
        "Files:",
        f"- {OFFICIAL_HTML}",
        f"- {OU_HTML}",
        f"- {OFFICIAL_JSON}",
        f"- {OU_JSON}",
        "",
        "Resolver detail tail:",
        resolver_detail or "-",
        "",
        "Rule: document reporting only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()

