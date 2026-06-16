from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import os
import re
import sys

try:
    import requests
except Exception as exc:
    print("ERROR: requests package missing:", exc)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

OU_JSON = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
LEDGER = ASTRO / "ou-aplus-telegram-sent-ledger.json"
OU_CSV = ASTRO / "ASTRODDS-clean-ou-record.csv"
REPORT = REPORTS / "136_send_ou_aplus_telegram_report.txt"

ET = ZoneInfo("America/New_York")
MIN_EDGE_RUNS = 1.75

CSV_FIELDS = [
    "date", "game", "pick", "result", "line", "projected",
    "edge_runs", "price", "stake", "status", "grade",
    "final_score", "total_runs", "resolved_at", "notes"
]

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

def to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def normalize_text(value):
    return str(value or "").strip()

def get_first(row, keys, default=""):
    for k in keys:
        if isinstance(row, dict) and k in row and row[k] not in (None, ""):
            return row[k]
    return default

def collect_dicts(obj):
    found = []
    if isinstance(obj, dict):
        if any(k in obj for k in ("game", "pick", "projected", "edgeRuns", "edge_runs", "line")):
            found.append(obj)
        for v in obj.values():
            found.extend(collect_dicts(v))
    elif isinstance(obj, list):
        for x in obj:
            found.extend(collect_dicts(x))
    return found

def parse_candidates(data):
    raw = []

    # Prefer explicit likely arrays if present.
    for key in ("candidates", "ouPicks", "ou_picks", "picks", "rows"):
        val = data.get(key) if isinstance(data, dict) else None
        if isinstance(val, list):
            raw.extend([x for x in val if isinstance(x, dict)])
            break

    # Fallback recursive search.
    if not raw:
        raw = collect_dicts(data)

    out = []
    for r in raw:
        game = normalize_text(get_first(r, ["game", "matchup", "name"]))
        pick = normalize_text(get_first(r, ["pick", "selection"]))
        if not game or not pick:
            continue

        category = normalize_text(get_first(r, ["category", "decision", "type", "tier"])).upper()
        line = to_float(get_first(r, ["line", "totalLine", "marketLine"]), None)
        projected = to_float(get_first(r, ["projected", "projectedTotal", "expectedTotal", "projectedTotalRuns"]), None)
        edge_runs = to_float(get_first(r, ["edgeRuns", "edge_runs", "valueGap", "gap"]), None)

        if edge_runs is None and line is not None and projected is not None:
            edge_runs = projected - line

        if line is None or projected is None or edge_runs is None:
            continue

        # A+ O/U only.
        if edge_runs < MIN_EDGE_RUNS:
            continue

        # If category exists and clearly says WATCH/LEAN, skip.
        if "WATCH" in category or "LEAN" in category:
            continue

        price = get_first(r, ["price", "odds", "marketPrice", "priceAmerican"], "")
        stake = get_first(r, ["stake"], "3% max / paper")

        out.append({
            "game": game,
            "pick": pick,
            "line": line,
            "projected": projected,
            "edge_runs": edge_runs,
            "price": str(price),
            "stake": str(stake),
            "grade": "A+",
        })

    # Dedupe and sort by highest value gap.
    seen = set()
    clean = []
    today = now_et().date().isoformat()
    for r in out:
        key = "|".join([today, r["game"], r["pick"], str(r["line"]), "ou_aplus"])
        if key in seen:
            continue
        seen.add(key)
        r["key"] = key
        clean.append(r)

    clean.sort(key=lambda x: -x["edge_runs"])
    return clean

def load_sent():
    if not LEDGER.exists():
        return {"sent": []}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": []}

def save_sent(data):
    LEDGER.write_text(json.dumps(data, indent=2), encoding="utf-8")

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()
    return r.json()

def build_message(r):
    price = r["price"] if r["price"] not in ("", "None") else "N/A"
    return (
        "ASTRODDS OVER/UNDER A+ PICK\n\n"
        f"Game: {r['game']}\n"
        f"Pick: {r['pick']}\n"
        f"Market Line: {r['line']:.1f} runs\n"
        f"Projected Total: {r['projected']:.2f} runs\n"
        f"Value Gap: +{r['edge_runs']:.2f} runs\n"
        f"Price: {price}\n"
        "Stake: 3% max / paper\n\n"
        "Simple read:\n"
        f"The market line is {r['line']:.1f}, but the bot projects {r['projected']:.2f} total runs.\n"
        f"That creates a +{r['edge_runs']:.2f} run gap.\n\n"
        "Rule: O/U A+ only = Value Gap >= +1.75 runs.\n"
        "Paper/manual only. No real-money automation."
    )

def read_ou_csv():
    if not OU_CSV.exists():
        return []
    with OU_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_ou_csv(rows):
    ASTRO.mkdir(parents=True, exist_ok=True)

    fields = []
    for f in CSV_FIELDS:
        if f not in fields:
            fields.append(f)
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)

    with OU_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def ou_csv_key(row):
    return "|".join([
        str(row.get("date", "")).strip(),
        str(row.get("game", "")).strip(),
        str(row.get("pick", "")).strip(),
        str(row.get("line", "")).strip(),
    ])

def sync_to_ou_csv(sent_candidates):
    rows = read_ou_csv()
    existing = {ou_csv_key(r) for r in rows if str(r.get("status", "")).strip() == "clean_ou_aplus"}
    today = now_et().date().isoformat()
    added = 0

    for r in sent_candidates:
        row = {
            "date": today,
            "game": r["game"],
            "pick": r["pick"],
            "result": "pending",
            "line": f"{r['line']:.1f}",
            "projected": f"{r['projected']:.2f}",
            "edge_runs": f"{r['edge_runs']:.2f}",
            "price": r["price"],
            "stake": "3%",
            "status": "clean_ou_aplus",
            "grade": "A+",
            "final_score": "",
            "total_runs": "",
            "resolved_at": "",
            "notes": "Auto-added from O/U A+ Telegram sender."
        }
        key = ou_csv_key(row)
        if key in existing:
            continue
        rows.append(row)
        existing.add(key)
        added += 1

    write_ou_csv(rows)
    return added

def main():
    load_env()
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    enabled = os.environ.get("ASTRODDS_SEND_OU_APLUS_TELEGRAM", "").lower() in ("1", "true", "yes")
    dry_run = os.environ.get("ASTRODDS_OU_APLUS_DRY_RUN", "").lower() in ("1", "true", "yes")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_SIGNALS_CHAT_ID", "").strip()

    data = load_json(OU_JSON, {})
    candidates = parse_candidates(data)
    ledger = load_sent()
    sent_set = set(ledger.get("sent", []))

    sent_now = 0
    skipped_duplicates = 0
    sent_candidates = []

    lines = [
        "ASTRODDS 136 SEND O/U A+ TELEGRAM",
        "=" * 52,
        f"Generated ET: {now_et().isoformat()}",
        f"Enabled: {enabled}",
        f"Dry run: {dry_run}",
        f"O/U JSON: {OU_JSON}",
        f"Min Value Gap: +{MIN_EDGE_RUNS:.2f} runs",
        f"Candidates found: {len(candidates)}",
        ""
    ]

    if not enabled:
        lines.append("STOP: ASTRODDS_SEND_OU_APLUS_TELEGRAM is not true.")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    for r in candidates:
        if r["key"] in sent_set:
            skipped_duplicates += 1
            lines.append(f"SKIP DUPLICATE | {r['pick']} | {r['game']}")
            continue

        if dry_run:
            lines.append(
                f"DRY RUN | {r['pick']} | {r['game']} | "
                f"Line={r['line']:.1f} Projected={r['projected']:.2f} Gap=+{r['edge_runs']:.2f}"
            )
            continue

        if not token or not chat_id:
            lines.append("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_SIGNALS_CHAT_ID missing.")
            REPORT.write_text("\n".join(lines), encoding="utf-8")
            sys.exit(3)

        send_message(token, chat_id, build_message(r))
        sent_set.add(r["key"])
        sent_candidates.append(r)
        sent_now += 1
        lines.append(f"SENT | {r['pick']} | {r['game']} | Gap=+{r['edge_runs']:.2f}")

    csv_added = 0
    if sent_candidates:
        csv_added = sync_to_ou_csv(sent_candidates)

    ledger["sent"] = sorted(sent_set)
    ledger["updatedAt"] = now_et().isoformat()
    save_sent(ledger)

    lines.extend([
        "",
        "Summary:",
        f"- Sent now: {sent_now}",
        f"- Skipped duplicates: {skipped_duplicates}",
        f"- Added to O/U CSV pending: {csv_added}",
        "",
        "Rule: O/U A+ Telegram only. No betting automation."
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()

