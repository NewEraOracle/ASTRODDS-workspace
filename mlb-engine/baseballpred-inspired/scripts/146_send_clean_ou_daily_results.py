from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
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

OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
SENT_LEDGER = ASTRO / "ASTRODDS-clean-ou-daily-results-sent-ledger.json"
REPORT = REPORTS / "146_clean_ou_daily_results_report.txt"
HTML_REPORT = ASTRO / "astrodds-clean-ou-results.html"

ET = ZoneInfo("America/New_York")

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

def read_rows():
    if not OU_CSV.exists():
        return []
    with OU_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if str(r.get("status", "")).strip() == "clean_ou_aplus"]

def count(rows, result):
    return sum(1 for r in rows if str(r.get("result", "")).strip().lower() == result)

def esc(v):
    return str(v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def load_sent():
    if not SENT_LEDGER.exists():
        return {"sent": []}
    try:
        return json.loads(SENT_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": []}

def save_sent(data):
    SENT_LEDGER.write_text(json.dumps(data, indent=2), encoding="utf-8")

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()

def send_document(token, chat_id, path, caption):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (Path(path).name, f, "text/html")},
            timeout=60,
        )
    r.raise_for_status()

def build_html(rows, generated_date):
    wins = count(rows, "win")
    losses = count(rows, "loss")
    pushes = count(rows, "push")
    pending = count(rows, "pending")
    resolved = wins + losses
    win_rate = (100 * wins / resolved) if resolved else 0.0

    latest_date = sorted({r.get("date", "") for r in rows})[-1] if rows else ""
    latest_rows = [r for r in rows if r.get("date", "") == latest_date]
    day_wins = count(latest_rows, "win")
    day_losses = count(latest_rows, "loss")
    day_pushes = count(latest_rows, "push")
    day_pending = count(latest_rows, "pending")

    tr = ""
    for r in rows:
        res = str(r.get("result", "")).upper()
        cls = "win" if res == "WIN" else "loss" if res == "LOSS" else "pending"
        tr += f"""
        <tr>
          <td>{esc(r.get('date'))}</td>
          <td>{esc(r.get('game'))}</td>
          <td>{esc(r.get('pick'))}</td>
          <td>{esc(r.get('line'))}</td>
          <td>{esc(r.get('projected'))}</td>
          <td>{esc(r.get('edge_runs'))}</td>
          <td>{esc(r.get('total_runs'))}</td>
          <td class="{cls}">{esc(res)}</td>
        </tr>
        """

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ASTRODDS Clean O/U Results</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;margin:0;padding:28px;color:#111827}}
.card{{max-width:1150px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:28px;box-shadow:0 8px 24px rgba(15,23,42,.06)}}
h1{{margin:0 0 8px;font-size:34px}}
.sub{{color:#374151;font-size:18px;margin-bottom:24px}}
.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:26px}}
.box{{background:#f1f5f9;border-radius:12px;padding:16px}}
.label{{color:#374151;font-size:14px;margin-bottom:4px}}
.value{{font-size:28px;font-weight:800}}
table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:15px}}
th{{text-align:left;border-bottom:2px solid #e5e7eb;padding:12px 10px}}
td{{border-bottom:1px solid #e5e7eb;padding:12px 10px}}
.win{{color:#047857;font-weight:800}}
.loss{{color:#b91c1c;font-weight:800}}
.pending{{color:#92400e;font-weight:800}}
.footer{{margin-top:24px;color:#6b7280;font-size:14px}}
</style>
</head>
<body>
<div class="card">
<h1>ASTRODDS Clean O/U A+ Results</h1>
<div class="sub">Only Over/Under A+ signals. Rule: Value Gap >= +1.75 runs.</div>
<div class="stats">
  <div class="box"><div class="label">Record</div><div class="value">{wins}-{losses}</div></div>
  <div class="box"><div class="label">Win Rate</div><div class="value">{win_rate:.1f}%</div></div>
  <div class="box"><div class="label">Pushes</div><div class="value">{pushes}</div></div>
  <div class="box"><div class="label">Latest Day</div><div class="value">{day_wins}-{day_losses}</div></div>
  <div class="box"><div class="label">Pending</div><div class="value">{pending}</div></div>
</div>
<h2>All Clean O/U A+ Picks</h2>
<table>
<thead><tr><th>Date</th><th>Game</th><th>Pick</th><th>Line</th><th>Projected</th><th>Gap</th><th>Total Runs</th><th>Result</th></tr></thead>
<tbody>{tr}</tbody>
</table>
<div class="footer">
Latest clean day: {esc(latest_date)} = {day_wins}-{day_losses}, pushes {day_pushes}, pending {day_pending}<br>
Overall clean O/U A+ record: {wins}-{losses}, win rate {win_rate:.1f}%, pushes {pushes}<br>
Generated: {esc(generated_date)} ET<br>
Paper/manual only. No real-money automation.
</div>
</div>
</body>
</html>"""

def main():
    load_env()
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    dry_run = os.environ.get("ASTRODDS_CLEAN_OU_RESULTS_DRY_RUN", "").lower() in ("1", "true", "yes")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_SIGNALS_CHAT_ID", "").strip()

    rows = read_rows()
    wins = count(rows, "win")
    losses = count(rows, "loss")
    pushes = count(rows, "push")
    pending = count(rows, "pending")
    resolved = wins + losses
    win_rate = (100 * wins / resolved) if resolved else 0.0

    latest_date = sorted({r.get("date", "") for r in rows})[-1] if rows else ""
    latest_rows = [r for r in rows if r.get("date", "") == latest_date]
    day_wins = count(latest_rows, "win")
    day_losses = count(latest_rows, "loss")
    day_pushes = count(latest_rows, "push")
    day_pending = count(latest_rows, "pending")

    generated_date = datetime.now(ET).date().isoformat()
    key = f"{generated_date}|clean_ou_daily_results"

    game_lines = "\n".join(
        f"- {r.get('date')} | {r.get('result','').upper()} | {r.get('pick')} | {r.get('game')} | Total={r.get('total_runs','')}"
        for r in rows
    ) if rows else "- none"

    text = (
        "ASTRODDS CLEAN O/U A+ RESULTS\n"
        f"Date: {generated_date}\n\n"
        f"Overall Record: {wins}-{losses}\n"
        f"Win Rate: {win_rate:.1f}%\n"
        f"Pushes: {pushes}\n"
        f"Pending: {pending}\n\n"
        f"Latest Day ({latest_date}): {day_wins}-{day_losses}, Push {day_pushes}, Pending {day_pending}\n\n"
        "All Clean O/U A+ Picks:\n"
        f"{game_lines}\n\n"
        "Rule: O/U A+ only = Value Gap >= +1.75 runs.\n"
        "Paper/manual only. No real-money automation."
    )

    HTML_REPORT.write_text(build_html(rows, generated_date), encoding="utf-8")

    lines = [
        "ASTRODDS 146 CLEAN O/U DAILY RESULTS",
        "=" * 52,
        f"Generated ET: {datetime.now(ET).isoformat()}",
        f"Dry run: {dry_run}",
        f"CSV: {OU_CSV}",
        f"HTML: {HTML_REPORT}",
        "",
        text,
    ]

    sent = load_sent()
    already_sent = key in sent.get("sent", [])

    if dry_run:
        lines.append("")
        lines.append("DRY RUN ONLY - Telegram not sent.")
    elif already_sent:
        lines.append("")
        lines.append("Skipped Telegram: already sent for this ET date.")
    else:
        if not token or not chat_id:
            lines.append("ERROR: missing Telegram token/chat id.")
            REPORT.write_text("\n".join(lines), encoding="utf-8")
            sys.exit(3)

        send_message(token, chat_id, text)
        send_document(token, chat_id, HTML_REPORT, "ASTRODDS clean O/U A+ results report")

        sent.setdefault("sent", []).append(key)
        sent["updatedAt"] = datetime.now(ET).isoformat()
        save_sent(sent)
        lines.append("")
        lines.append("Telegram sent: clean O/U summary + HTML report.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
