from pathlib import Path
import json
import csv
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENV = ROOT / ".env.local"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
PROOF = ROOT / "public" / "astrodds-proof-log.json"
DUP_LEDGER = ROOT / ".astrodds" / "ASTRODDS-telegram-weekly-results-ledger.json"

OUT_JSON = ROOT / ".astrodds" / "ASTRODDS-weekly-results-latest.json"
OUT_CSV = ROOT / ".astrodds" / "ASTRODDS-weekly-results-latest.csv"
PUBLIC_CSV = ROOT / "public" / "astrodds-weekly-results-latest.csv"
PUBLIC_HTML = ROOT / "public" / "astrodds-weekly-results-latest.html"
REPORT = BASE / "reports" / "64_weekly_investor_results_report.txt"

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
    dt = parse_dt(row.get("date") or row.get("gameDate") or row.get("commenceTime") or row.get("resolvedAt") or row.get("loggedAt"))
    if not dt:
        return None
    return dt.astimezone(TZ).date()

def current_week_range():
    today = datetime.now(TZ).date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end

def get_rows_from_ledger():
    ledger = read_json(LEDGER, [])
    if isinstance(ledger, list):
        return [r for r in ledger if isinstance(r, dict)], "engine_signal_ledger"
    return [], "engine_signal_ledger_missing"

def get_rows_from_proof():
    proof = read_json(PROOF, {})
    rows = []
    if isinstance(proof, dict) and isinstance(proof.get("rows"), list):
        rows = proof.get("rows")
    elif isinstance(proof, list):
        rows = proof
    return [r for r in rows if isinstance(r, dict)], "public_proof_log"

def filter_week(rows, start, end):
    out = []
    for r in rows:
        d = row_montreal_date(r)
        if d and start <= d <= end:
            out.append(r)
    return out

def result_key(row):
    return str(row.get("result", "pending")).lower()

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
    wins = sum(1 for r in rows if result_key(r) == "win")
    losses = sum(1 for r in rows if result_key(r) == "loss")
    pending = sum(1 for r in rows if result_key(r) not in ["win", "loss", "push", "void"])
    resolved = wins + losses
    wr = round((wins / resolved) * 100, 1) if resolved else None
    units = round(sum(fnum(r.get("paperProfitUnits")) for r in rows), 3)
    official = sum(1 for r in rows if str(r.get("finalEngineDecision", "")).upper() == "ENGINE_BUY" or str(r.get("decision", "")).upper() == "ENGINE_BUY")
    return {
        "signals": len(rows),
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "resolved": resolved,
        "winRatePct": wr,
        "paperUnits": units,
        "officialBuys": official,
    }

def score(row):
    away = row.get("awayRuns", "-")
    home = row.get("homeRuns", "-")
    if away == "-" and home == "-":
        return row.get("score", "-")
    return f"{away}-{home}"

def csv_rows(rows):
    out = []
    for r in rows:
        d = row_montreal_date(r)
        out.append({
            "Date": d.isoformat() if d else "",
            "Game": r.get("game", ""),
            "Pick": r.get("pick", ""),
            "Decision": r.get("finalEngineDecision") or r.get("decision", ""),
            "Grade": r.get("finalGrade") or r.get("grade", ""),
            "Category": category(r),
            "Result": r.get("result", "pending"),
            "Winner": r.get("winner", ""),
            "Score": score(r),
            "Paper Units": r.get("paperProfitUnits", 0),
            "Paper Only": True,
        })
    return out

def write_csv(path, rows):
    fields = ["Date", "Game", "Pick", "Decision", "Grade", "Category", "Result", "Winner", "Score", "Paper Units", "Paper Only"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})

def telegram_send(token, chat_id, text):
    if not token or not chat_id:
        return False, "missing token/chat"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return True, resp.read().decode("utf-8", errors="ignore")[:500]

def telegram_send_document(token, chat_id, file_path, caption):
    if not token or not chat_id:
        return False, "missing token/chat"
    boundary = "----ASTRODDSBoundary"
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    file_bytes = file_path.read_bytes()
    parts = []
    def add_field(name, value):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    add_field("chat_id", chat_id)
    add_field("caption", caption)
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{file_path.name}\"\r\nContent-Type: text/csv\r\n\r\n".encode("utf-8"))
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return True, resp.read().decode("utf-8", errors="ignore")[:500]

def build_message(start, end, s):
    wr = "N/A" if s["winRatePct"] is None else f"{s['winRatePct']:.1f}%"
    return "\n".join([
        "ASTRODDS WEEKLY RESULTS",
        f"Week: {start.isoformat()} to {end.isoformat()}",
        "",
        f"Signals: {s['signals']}",
        f"Wins: {s['wins']}",
        f"Losses: {s['losses']}",
        f"Pending: {s['pending']}",
        f"Win rate: {wr}",
        f"Paper units: {s['paperUnits']:.3f}u",
        f"Official buys: {s['officialBuys']}",
        "",
        "CSV attached for Google Sheets.",
        "Paper/manual only. No real-money automation.",
    ])

def build_html(start, end, summary, rows):
    wr = "N/A" if summary["winRatePct"] is None else f"{summary['winRatePct']:.1f}%"
    trs = []
    for r in rows:
        trs.append(f"<tr><td>{r['Date']}</td><td>{r['Game']}</td><td>{r['Pick']}</td><td>{r['Category']}</td><td>{r['Result']}</td><td>{r['Score']}</td><td>{r['Paper Units']}</td></tr>")
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>ASTRODDS Weekly Results</title></head><body>
<h1>ASTRODDS Weekly Results</h1>
<p>Week: {start.isoformat()} to {end.isoformat()}</p>
<p>Signals: {summary['signals']} | Wins: {summary['wins']} | Losses: {summary['losses']} | Win rate: {wr} | Units: {summary['paperUnits']:.3f}u</p>
<table border='1' cellpadding='6'><tr><th>Date</th><th>Game</th><th>Pick</th><th>Category</th><th>Result</th><th>Score</th><th>Units</th></tr>{''.join(trs)}</table>
<p>Paper/manual only. No real-money automation.</p>
</body></html>"""

def main():
    generated = datetime.now(timezone.utc).isoformat()
    env = load_env(ENV)
    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("ASTRODDS_TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_RESULTS_CHAT_ID") or env.get("TELEGRAM_CHAT_ID") or env.get("ASTRODDS_TELEGRAM_CHAT_ID")

    start, end = current_week_range()
    week_key = f"{start.isoformat()}_{end.isoformat()}"

    ledger_rows, source = get_rows_from_ledger()
    week_rows = filter_week(ledger_rows, start, end)

    if not week_rows and ledger_rows:
        # Safety fallback for current small proof phase: do not show fake zero if ledger exists.
        week_rows = ledger_rows
        source = "engine_signal_ledger_all_rows_fallback"

    if not week_rows:
        proof_rows, proof_source = get_rows_from_proof()
        proof_week = filter_week(proof_rows, start, end)
        if proof_week:
            week_rows = proof_week
            source = proof_source

    summary = summarize(week_rows)
    rows = csv_rows(week_rows)

    write_json(OUT_JSON, {"generatedAt": generated, "weekStart": start.isoformat(), "weekEnd": end.isoformat(), "source": source, "summary": summary, "rows": rows, "paperOnly": True, "realMoneyAutomation": False})
    write_csv(OUT_CSV, rows)
    write_csv(PUBLIC_CSV, rows)
    PUBLIC_HTML.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_HTML.write_text(build_html(start, end, summary, rows), encoding="utf-8")

    dedupe = read_json(DUP_LEDGER, {})
    duplicate = (week_key in dedupe) if isinstance(dedupe, dict) else (week_key in dedupe if isinstance(dedupe, list) else False)

    msg = build_message(start, end, summary)
    sent_msg = False
    sent_doc = False
    err = ""
    if duplicate:
        status = "DUPLICATE"
    else:
        try:
            sent_msg, _ = telegram_send(token, chat_id, msg)
            sent_doc, _ = telegram_send_document(token, chat_id, PUBLIC_CSV, f"ASTRODDS weekly results {week_key}")
            status = "OK" if sent_msg and sent_doc else "ERROR"
            if status == "OK":
                if isinstance(dedupe, dict):
                    dedupe[week_key] = {"sentAt": generated, "summary": summary}
                else:
                    dedupe = list(dedupe) if isinstance(dedupe, list) else []
                    dedupe.append(week_key)
                write_json(DUP_LEDGER, dedupe)
        except Exception as exc:
            status = "ERROR"
            err = str(exc)

    lines = [
        "ASTRODDS 64 WEEKLY INVESTOR RESULTS REPORT",
        "=" * 56,
        f"Generated: {generated}",
        "",
        f"Status: {status}",
    ]
    if err:
        lines.append(f"Send error: {err}")
    lines += [
        f"Source: {source}",
        f"Week: {start.isoformat()} to {end.isoformat()}",
        f"Sent Telegram summary: {1 if sent_msg else 0}",
        f"Sent Telegram CSV: {1 if sent_doc else 0}",
        f"Skipped duplicate: {1 if duplicate else 0}",
        "",
        f"Signals: {summary['signals']}",
        f"Resolved: {summary['resolved']}",
        f"Wins: {summary['wins']}",
        f"Losses: {summary['losses']}",
        f"Pending: {summary['pending']}",
        f"Win rate: {summary['winRatePct']}%",
        f"Paper units: {summary['paperUnits']}u",
        "",
        f"Google Sheets CSV: {PUBLIC_CSV}",
        f"Investor HTML: {PUBLIC_HTML}",
        f"JSON: {OUT_JSON}",
        "Rule: weekly investor report only. No odds scan. No betting automation.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()