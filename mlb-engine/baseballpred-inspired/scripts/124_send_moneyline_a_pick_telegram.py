# -*- coding: utf-8 -*-
"""
ASTRODDS 124 - Send Moneyline A PICK Signals to Telegram

Purpose:
- Send public board A PICK moneyline signals to Telegram.
- Separate from official ENGINE_BUY/A+ verified record.
- Does NOT affect official record.
- Duplicate protected.

Safety:
- Sends only if ASTRODDS_SEND_MONEYLINE_APICK_TELEGRAM=true
- Paper/manual only
- No betting automation
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

BOARD_JSON = ROOT / ".astrodds" / "ASTRODDS-public-board-categories-latest.json"
SENT_LEDGER = ROOT / ".astrodds" / "moneyline-apick-telegram-sent-ledger.json"
REPORT = BASE / "reports" / "124_send_moneyline_a_pick_telegram_report.txt"

ET = ZoneInfo("America/Toronto")

def yn(value):
    return str(value or "").strip().lower() in ["1", "true", "yes", "y", "on"]

def get_env(*names):
    for name in names:
        v = os.getenv(name)
        if v:
            return v
    return None

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def pct(value):
    try:
        v = float(value)
        if v <= 1:
            return f"{v * 100:.2f}%"
        return f"{v:.2f}%"
    except Exception:
        return str(value or "-")

def money_price(value):
    if value is None:
        return "-"
    try:
        v = float(value)
        if v <= 1:
            return f"${v:.2f}"
        return str(value)
    except Exception:
        return str(value)

def first_present(d, names, default=None):
    for n in names:
        if isinstance(d, dict) and n in d and d[n] not in [None, ""]:
            return d[n]
    return default


def local_date_key(value):
    raw = str(value or "")
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return raw[:10]

def get_apicks(board):
    """
    Moneyline A PICK rule:
    - Include normal aPicks
    - Also promote valueLeans with edge >= 10%
    This prevents good A PICKs from being hidden as VALUE_LEAN.
    """
    if not isinstance(board, dict):
        return []

    out = []

    for key in ["aPick", "aPicks", "a_pick", "aPICK"]:
        if isinstance(board.get(key), list):
            out.extend(board.get(key))

    cats = board.get("categories")
    if isinstance(cats, dict):
        for key in ["aPick", "aPicks", "A PICK", "A_PICK"]:
            if isinstance(cats.get(key), list):
                out.extend(cats.get(key))

    rows = board.get("rows")
    if isinstance(rows, list):
        for r in rows:
            cat = str(first_present(r, ["category", "tier", "label"], "")).lower()
            if "a pick" in cat or cat == "apick" or cat == "a_pick":
                out.append(r)

    # Fix: promote VALUE_LEAN rows with edge >= 10% into A PICK Telegram.
    for key in ["valueLean", "valueLeans", "VALUE_LEAN"]:
        value_rows = board.get(key)
        if isinstance(value_rows, list):
            for r in value_rows:
                try:
                    edge = float(first_present(r, ["edge", "edgePct", "probabilityEdge"], 0))
                except Exception:
                    edge = 0
                model = float(first_present(r, ["model", "modelProb", "modelProbability", "probability"], 0) or 0)
                if edge >= 0.10 and model >= 0.62:
                    rr = dict(r)
                    rr["category"] = "A_PICK"
                    rr["stake"] = "5% bankroll"
                    rr["reason"] = "Promoted from VALUE_LEAN because edge is >= 10%."
                    out.append(rr)

    # De-dupe by stable game + pick + local date.
    deduped = []
    seen = set()
    for r in out:
        game = first_present(r, ["game", "market", "event", "matchup"], "")
        pick = first_present(r, ["pick", "team", "selection"], "")
        date = first_present(r, ["date", "commenceTime", "commence_time", "startTime"], "")
        key = "|".join([str(local_date_key(date)), str(game), str(pick)])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped

def make_signal_id(r):
    game = first_present(r, ["game", "market", "event", "matchup"], "")
    pick = first_present(r, ["pick", "team", "selection"], "")
    date = first_present(r, ["date", "commenceTime", "commence_time", "startTime"], "")
    # Stable duplicate key: do NOT include market price.
    # Price can move during the day; same pick should not be sent twice.
    return "|".join([str(local_date_key(date)), str(game), str(pick), "moneyline_apick"])


def local_time_label(value):
    raw = str(value or "")
    if not raw:
        return "-"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        local = dt.astimezone(ET)
        return local.strftime("%Y-%m-%d %I:%M %p ET")
    except Exception:
        return raw

def build_message(r):
    game = first_present(r, ["game", "market", "event", "matchup"], "-")
    pick = first_present(r, ["pick", "team", "selection"], "-")
    date = first_present(r, ["date", "commenceTime", "commence_time", "startTime"], "-")
    market = first_present(r, ["marketPrice", "market_price", "price", "market"], "-")
    model = first_present(r, ["model", "modelProb", "modelProbability", "probability"], "-")
    edge = first_present(r, ["edge", "edgePct", "probabilityEdge"], "-")
    stake = first_present(r, ["stake", "stakeText"], "5% bankroll / paper")

    return "\n".join([
        "ASTRODDS MONEYLINE A PICK",
        "",
        f"Pick: {pick}",
        f"Game: {game}",
        f"Time: {local_time_label(date)}",
        "",
        f"Market: {money_price(market)}",
        f"Model: {pct(model)}",
        f"Edge: {pct(edge)}",
        f"Stake: {stake}",
        "",
        "Rule: PAPER/MANUAL SIGNAL.",
        "This does not affect official verified A+ record until resolved.",
    ])

def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8")

def main():
    generated = datetime.now(ET).isoformat()

    enabled = yn(os.getenv("ASTRODDS_SEND_MONEYLINE_APICK_TELEGRAM"))
    token = get_env("ASTRODDS_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    chat_id = get_env("ASTRODDS_TELEGRAM_CHAT_ID", "TELEGRAM_SIGNALS_CHAT_ID", "TELEGRAM_CHAT_ID")

    board = read_json(BOARD_JSON, {})
    sent = read_json(SENT_LEDGER, {"sent": []})
    sent_ids = set(sent.get("sent", []))

    apicks = get_apicks(board)

    sent_now = []
    skipped_dup = []
    errors = []

    if not enabled:
        errors.append("disabled: set ASTRODDS_SEND_MONEYLINE_APICK_TELEGRAM=true")
    elif not token or not chat_id:
        errors.append("missing telegram token/chat id")
    else:
        for r in apicks:
            sid = make_signal_id(r)
            if sid in sent_ids:
                skipped_dup.append(sid)
                continue
            try:
                send_telegram(token, chat_id, build_message(r))
                sent_now.append(sid)
                sent_ids.add(sid)
            except Exception as e:
                errors.append(f"send_error:{sid}:{type(e).__name__}:{e}")

    sent["updatedAt"] = generated
    sent["sent"] = sorted(sent_ids)
    write_json(SENT_LEDGER, sent)

    lines = [
        "ASTRODDS 124 SEND MONEYLINE A PICK TELEGRAM",
        "=" * 62,
        f"Generated: {generated}",
        "",
        "Rules:",
        "- Sends public board A PICK moneyline signals.",
        "- Paper/manual only.",
        "- Does not affect official verified A+ record.",
        "- Duplicate protected.",
        "",
        f"Enabled: {enabled}",
        f"A PICK candidates found: {len(apicks)}",
        f"Sent now: {len(sent_now)}",
        f"Skipped duplicates: {len(skipped_dup)}",
        "",
        "Candidates:",
    ]

    for r in apicks:
        lines.append(
            f"- {first_present(r, ['pick','team','selection'], '-')} | "
            f"{first_present(r, ['game','market','event','matchup'], '-')} | "
            f"Market={money_price(first_present(r, ['marketPrice','market_price','price','market'], '-'))} | "
            f"Model={pct(first_present(r, ['model','modelProb','modelProbability','probability'], '-'))} | "
            f"Edge={pct(first_present(r, ['edge','edgePct','probabilityEdge'], '-'))}"
        )

    if errors:
        lines += ["", "Errors/warnings:"]
        for e in errors:
            lines.append(f"- {e}")

    lines += [
        "",
        f"Board JSON: {BOARD_JSON}",
        f"Sent ledger: {SENT_LEDGER}",
        "",
        "Rule: moneyline A PICK Telegram only. No betting automation.",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()






