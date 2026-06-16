from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import sys

try:
    import requests
except Exception as exc:
    print("ERROR: requests package missing:", exc)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"
LEDGER = ASTRO / "moneyline-a-aplus-telegram-sent-ledger.json"
REPORT = REPORTS / "135_send_moneyline_a_aplus_telegram_report.txt"

ET = ZoneInfo("America/New_York")

def now_et():
    return datetime.now(ET)

def load_env():
    env_file = ROOT / ".env.local"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def prob(value):
    try:
        x = float(value)
    except Exception:
        return 0.0
    if x > 1.5:
        x = x / 100.0
    return x

def et_date(value):
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return s[:10]

def et_time_text(value):
    s = str(value or "").strip()
    if not s:
        return "TBD"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(ET).strftime("%Y-%m-%d %I:%M %p ET")
    except Exception:
        return s

def classify(model, edge):
    if model >= 0.65 and edge >= 0.15:
        return "A+"
    if model >= 0.62 and edge >= 0.12:
        return "A"
    return ""

def get_candidates(board):
    # Main source: public board A picks.
    picks = board.get("aPicks", []) or board.get("a_picks", []) or []

    # Fallbacks, in case the board format changes later.
    if not picks:
        picks = board.get("picks", []) or board.get("rows", []) or []

    out = []
    today = now_et().date().isoformat()

    for r in picks:
        game = str(r.get("game", "")).strip()
        pick = str(r.get("pick", "")).strip()
        date_raw = r.get("date", r.get("commence_time", ""))

        if not game or not pick:
            continue

        local_date = et_date(date_raw)
        if local_date != today:
            continue

        model = prob(r.get("model", r.get("modelProb", r.get("confidence", r.get("probability", 0)))))
        edge = prob(r.get("edge", r.get("valueEdge", r.get("probEdge", 0))))
        market = r.get("market", r.get("price", ""))

        grade = classify(model, edge)
        if not grade:
            continue

        out.append({
            "grade": grade,
            "game": game,
            "pick": pick,
            "date": date_raw,
            "time_text": et_time_text(date_raw),
            "model": model,
            "edge": edge,
            "market": market,
            "stake": r.get("stake", "5% bankroll"),
        })

    # Stable dedupe: date ET + game + pick. Market price changes do not resend.
    seen = set()
    clean = []
    for r in out:
        key = "|".join([et_date(r["date"]), r["game"], r["pick"], "moneyline_a_aplus"])
        if key in seen:
            continue
        seen.add(key)
        r["key"] = key
        clean.append(r)

    # A+ first, then highest edge.
    clean.sort(key=lambda x: (0 if x["grade"] == "A+" else 1, -x["edge"], -x["model"]))
    return clean

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()
    return r.json()

def build_message(r):
    title = "ASTRODDS MONEYLINE A+ PICK" if r["grade"] == "A+" else "ASTRODDS MONEYLINE A PICK"
    safety = "Higher confidence / stronger value" if r["grade"] == "A+" else "Strong pick, but not A+"

    market = r["market"]
    try:
        market_txt = f"${float(market):.2f}"
    except Exception:
        market_txt = str(market or "N/A")

    return (
        f"{title}\n\n"
        f"Pick: {r['pick']}\n"
        f"Game: {r['game']}\n"
        f"Time: {r['time_text']}\n\n"
        f"Confidence: {r['model'] * 100:.0f}/100\n"
        f"Value Edge: {r['edge'] * 100:.2f}%\n"
        f"Market: {market_txt}\n"
        f"Safety: {safety}\n"
        f"Stake: {r['stake']}\n\n"
        "Rule: PAPER/MANUAL SIGNAL.\n"
        "A+ = 65+ confidence and 15%+ edge.\n"
        "A = 62+ confidence and 12%+ edge.\n"
        "No real-money automation."
    )

def main():
    load_env()
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    enabled = os.environ.get("ASTRODDS_SEND_MONEYLINE_APICK_TELEGRAM", "").lower() in ("1", "true", "yes")
    dry_run = os.environ.get("ASTRODDS_AAPLUS_DRY_RUN", "").lower() in ("1", "true", "yes")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_SIGNALS_CHAT_ID", "").strip()

    board = load_json(BOARD_JSON, {})
    candidates = get_candidates(board)
    ledger = load_json(LEDGER, {"sent": []})
    sent_set = set(ledger.get("sent", []))

    sent_now = 0
    skipped_duplicates = 0

    lines = [
        "ASTRODDS 135 SEND MONEYLINE A/A+ TELEGRAM",
        "=" * 60,
        f"Generated ET: {now_et().isoformat()}",
        f"Enabled: {enabled}",
        f"Dry run: {dry_run}",
        f"Board JSON: {BOARD_JSON}",
        f"Candidates found: {len(candidates)}",
        "",
    ]

    if not enabled:
        lines.append("STOP: ASTRODDS_SEND_MONEYLINE_APICK_TELEGRAM is not true.")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    for r in candidates:
        if r["key"] in sent_set:
            skipped_duplicates += 1
            lines.append(f"SKIP DUPLICATE | {r['grade']} | {r['pick']} | {r['game']}")
            continue

        msg = build_message(r)

        if dry_run:
            lines.append(f"DRY RUN | {r['grade']} | {r['pick']} | {r['game']}")
        else:
            if not token or not chat_id:
                lines.append("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_SIGNALS_CHAT_ID missing.")
                REPORT.write_text("\n".join(lines), encoding="utf-8")
                sys.exit(3)

            send_message(token, chat_id, msg)
            sent_set.add(r["key"])
            ledger["sent"] = sorted(sent_set)
            ledger["updatedAt"] = now_et().isoformat()
            save_json(LEDGER, ledger)
            sent_now += 1
            lines.append(f"SENT | {r['grade']} | {r['pick']} | {r['game']}")

    lines.extend([
        "",
        "Summary:",
        f"- Sent now: {sent_now}",
        f"- Skipped duplicates: {skipped_duplicates}",
        "",
        "Rule: A/A+ Moneyline Telegram only. No betting automation."
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()

