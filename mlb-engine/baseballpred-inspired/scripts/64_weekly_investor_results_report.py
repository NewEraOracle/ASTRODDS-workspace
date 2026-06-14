from pathlib import Path
import json
import csv
import html
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENV = ROOT / ".env.local"
LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
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
    dt = parse_dt(row.get("date") or row.get("commenceTime") or row.get("gameTime"))
    if not dt:
        dt = parse_dt(row.get("resolvedAt") or row.get("ledgerAddedAt"))
    if not dt:
        return None
    return dt.astimezone(TZ).date()

def fnum(value):
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

def pct(value):
    try:
        if value is None or str(value).strip() == "":
            return ""
        v = float(str(value).replace(",", "."))
        if v <= 1:
            v *= 100
        return round(v, 2)
    except Exception:
        return ""

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

def week_range():
    today = datetime.now(TZ).date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end

def summarize(rows):
    wins = [r for r in rows if result_key(r) == "win"]
    losses = [r for r in rows if result_key(r) == "loss"]
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
        "pending": len(pending),
        "winRatePct": win_rate,
        "paperUnits": units,
        "engineBuy": sum(1 for r in rows if str(r.get("finalEngineDecision") or "").upper() == "ENGINE_BUY"),
        "byCategory": by_cat,
    }

def score(row):
    away = row.get("awayRuns", "-")
    home = row.get("homeRuns", "-")
    return f"{away}-{home}"

def csv_rows(rows):
    out = []
    for r in rows:
        out.append({
            "Date": str(row_montreal_date(r) or ""),
            "Game": r.get("game", ""),
            "Pick": r.get("pick", ""),
            "Decision": r.get("finalEngineDecision", ""),
            "Grade": r.get("finalGrade", ""),
            "Category": category(r),
            "Market %": pct(r.get("marketProbability")),
            "Calibrated %": pct(r.get("calibratedProbabilityV2")),
            "Edge %": r.get("calibratedEdgePct", ""),
            "Result": r.get("result", "pending"),
            "Winner": r.get("winner", ""),
            "Score": score(r),
            "Paper Units": r.get("paperProfitUnits", 0),
            "Game UTC": r.get("date", ""),
            "Resolved At": r.get("resolvedAt", ""),
            "Paper Only": True,
        })
    return out

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "Date", "Game", "Pick", "Decision", "Grade", "Category",
        "Market %", "Calibrated %", "Edge %", "Result", "Winner",
        "Score", "Paper Units", "Game UTC", "Resolved At", "Paper Only"
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})

def build_html(start, end, summary, rows):
    def safe(x):
        return html.escape(str(x if x is not None else ""))
    wr = "N/A" if summary["winRatePct"] is None else f"{summary['winRatePct']}%"
    trs = []
    for r in rows:
        trs.append(
            "<tr>"
            f"<td>{safe(r['Date'])}</td>"
            f"<td>{safe(r['Game'])}</td>"
            f"<td><strong>{safe(r['Pick'])}</strong></td>"
            f"<td>{safe(r['Category'])}</td>"
            f"<td>{safe(r['Result']).upper()}</td>"
            f"<td>{safe(r['Score'])}</td>"
            f"<td>{safe(r['Paper Units'])}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ASTRODDS Weekly Results</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ margin:0; background:#07070a; color:#f4f4f5; font-family:Arial, Helvetica, sans-serif; }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:30px 18px; }}
    .cards {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin:20px 0; }}
    .card {{ background:#111118; border:1px solid #27272a; border-radius:14px; padding:16px; }}
    .label {{ color:#a1a1aa; font-size:12px; text-transform:uppercase; }}
    .value {{ font-size:24px; font-weight:800; margin-top:8px; }}
    table {{ width:100%; border-collapse:collapse; background:#101016; border:1px solid #27272a; }}
    th,td {{ padding:10px; border-bottom:1px solid #27272a; font-size:13px; text-align:left; }}
    th {{ background:#18181f; color:#d4d4d8; text-transform:uppercase; font-size:11px; }}
    .sub,.note {{ color:#a1a1aa; line-height:1.5; }}
    @media(max-width:900px) {{ .cards {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} table {{ display:block; overflow-x:auto; }} }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>ASTRODDS Weekly Results</h1>
  <div class="sub">Week: {safe(start)} to {safe(end)}. Paper/manual tracking only. No real-money automation.</div>
  <div class="cards">
    <div class="card"><div class="label">Signals</div><div class="value">{summary['signals']}</div></div>
    <div class="card"><div class="label">Wins</div><div class="value">{summary['wins']}</div></div>
    <div class="card"><div class="label">Losses</div><div class="value">{summary['losses']}</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="value">{wr}</div></div>
    <div class="card"><div class="label">Paper Units</div><div class="value">{summary['paperUnits']}u</div></div>
  </div>
  <table>
    <thead><tr><th>Date</th><th>Game</th><th>Pick</th><th>Category</th><th>Result</th><th>Score</th><th>Units</th></tr></thead>
    <tbody>{''.join(trs)}</tbody>
  </table>
  <p class="note">CSV is Google Sheets compatible: public/astrodds-weekly-results-latest.csv</p>
</div>
</body>
</html>"""

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
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{file_path.name}\"\r\nContent-Type: text/csv\r\n\r\n".encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        response = resp.read().decode("utf-8", errors="ignore")
    return True, response[:500]

def build_message(start, end, summary):
    wr = "N/A" if summary["winRatePct"] is None else f"{summary['winRatePct']}%"
    lines = []
    lines.append(f"ðŸ“ˆ ASTRODDS WEEKLY RESULTS")
    lines.append(f"Week: {start} to {end}")
    lines.append("")
    lines.append(f"Signals: {summary['signals']}")
    lines.append(f"Wins: {summary['wins']} | Losses: {summary['losses']} | Pending: {summary['pending']}")
    lines.append(f"Win rate: {wr}")
    lines.append(f"Paper units: {summary['paperUnits']}u")
    lines.append(f"Official buys: {summary['engineBuy']}")
    lines.append("")
    lines.append("CSV attached for Google Sheets.")
    lines.append("Paper/manual tracking only. No real-money automation.")
    return "\n".join(lines)

def main():
    generated = datetime.now(timezone.utc).isoformat()
    env = load_env(ENV)
    token = env.get("TELEGRAM_BOT_TOKEN") or env.get("ASTRODDS_TELEGRAM_BOT_TOKEN")
    chat_id = (
        env.get("TELEGRAM_RESULTS_CHAT_ID")
        or env.get("TELEGRAM_CHAT_ID")
        or env.get("ASTRODDS_TELEGRAM_CHAT_ID")
    )

    start, end = week_range()
    week_key = f"{start.isoformat()}_{end.isoformat()}"

    ledger = read_json(LEDGER, [])
    if not isinstance(ledger, list):
        ledger = []

    week_rows_raw = []
    for r in ledger:
        d = row_montreal_date(r)
        if d and start <= d <= end:
            week_rows_raw.append(r)

    summary = summarize(week_rows_raw)
    rows = csv_rows(week_rows_raw)

    write_json(OUT_JSON, {
        "generatedAt": generated,
        "weekStart": start.isoformat(),
        "weekEnd": end.isoformat(),
        "summary": summary,
        "rows": rows,
        "paperOnly": True,
        "realMoneyAutomation": False,
    })
    write_csv(OUT_CSV, rows)
    write_csv(PUBLIC_CSV, rows)
    PUBLIC_HTML.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_HTML.write_text(build_html(start, end, summary, rows), encoding="utf-8")

    dup = read_json(DUP_LEDGER, {})
    if not isinstance(dup, dict):
        dup = {}
    duplicate = week_key in dup

    msg = build_message(start, end, summary)

    sent_msg = False
    sent_doc = False
    send_error = ""
    if duplicate:
        status = "DUPLICATE"
    else:
        try:
            sent_msg, _ = telegram_send(token, chat_id, msg)
            sent_doc, _ = telegram_send_document(token, chat_id, PUBLIC_CSV, f"ASTRODDS weekly results {week_key}")
            status = "OK" if sent_msg and sent_doc else "ERROR"
            if status == "OK":
                dup[week_key] = {"sentAt": generated, "weekStart": start.isoformat(), "weekEnd": end.isoformat(), "summary": summary}
                write_json(DUP_LEDGER, dup)
        except Exception as exc:
            status = "ERROR"
            send_error = str(exc)

    report_lines = []
    report_lines.append("ASTRODDS 64 WEEKLY INVESTOR RESULTS REPORT")
    report_lines.append("=" * 56)
    report_lines.append(f"Generated: {generated}")
    report_lines.append("")
    report_lines.append(f"Status: {status}")
    if send_error:
        report_lines.append(f"Send error: {send_error}")
    report_lines.append(f"Week: {start} to {end}")
    report_lines.append(f"Sent Telegram summary: {1 if sent_msg else 0}")
    report_lines.append(f"Sent Telegram CSV: {1 if sent_doc else 0}")
    report_lines.append(f"Skipped duplicate: {1 if duplicate else 0}")
    report_lines.append("")
    report_lines.append(f"Signals: {summary['signals']}")
    report_lines.append(f"Resolved: {summary['resolved']}")
    report_lines.append(f"Wins: {summary['wins']}")
    report_lines.append(f"Losses: {summary['losses']}")
    report_lines.append(f"Pending: {summary['pending']}")
    report_lines.append(f"Win rate: {summary['winRatePct']}%")
    report_lines.append(f"Paper units: {summary['paperUnits']}u")
    report_lines.append("")
    report_lines.append(f"Google Sheets CSV: {PUBLIC_CSV}")
    report_lines.append(f"Investor HTML: {PUBLIC_HTML}")
    report_lines.append(f"JSON: {OUT_JSON}")
    report_lines.append("")
    report_lines.append("Rule: weekly investor report only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(report_lines), encoding="utf-8")
    print("\n".join(report_lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

