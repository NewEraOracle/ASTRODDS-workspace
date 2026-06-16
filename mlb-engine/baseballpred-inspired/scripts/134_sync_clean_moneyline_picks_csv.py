from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-public-board-categories-latest.json"
CLEAN_CSV = ASTRO / "ASTRODDS-clean-moneyline-record.csv"
REPORT = REPORTS / "134_sync_clean_moneyline_picks_csv_report.txt"

ET = ZoneInfo("America/New_York")

FIELDS = [
    "date", "game", "pick", "result", "model", "edge", "stake",
    "status", "grade", "market", "final_score", "resolved_at", "notes"
]


def now_et():
    return datetime.now(ET)


def parse_iso_to_et_date(value):
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(ET).date().isoformat()
    except Exception:
        return s[:10]


def norm_prob(value):
    try:
        x = float(value)
    except Exception:
        return 0.0
    if x > 1.5:
        x = x / 100.0
    return x


def pct_str(value):
    x = norm_prob(value)
    return f"{x * 100:.2f}"


def read_board():
    if not BOARD_JSON.exists():
        raise FileNotFoundError(f"Missing board JSON: {BOARD_JSON}")
    return json.loads(BOARD_JSON.read_text(encoding="utf-8"))


def read_csv_rows():
    if not CLEAN_CSV.exists():
        return []
    with CLEAN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(rows):
    ASTRO.mkdir(parents=True, exist_ok=True)

    existing_fields = []
    for r in rows:
        for k in r.keys():
            if k not in existing_fields:
                existing_fields.append(k)

    fields = []
    for k in FIELDS:
        if k not in fields:
            fields.append(k)
    for k in existing_fields:
        if k not in fields:
            fields.append(k)

    if CLEAN_CSV.exists():
        backup = CLEAN_CSV.with_suffix(".before-134-sync.csv")
        try:
            backup.write_text(CLEAN_CSV.read_text(encoding="utf-8-sig"), encoding="utf-8")
        except Exception:
            pass

    with CLEAN_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def row_key(row):
    return "|".join([
        str(row.get("date", "")).strip(),
        str(row.get("game", "")).strip(),
        str(row.get("pick", "")).strip(),
    ])


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    board = read_board()
    rows = read_csv_rows()

    existing = {row_key(r) for r in rows if str(r.get("status", "")).strip() == "clean_apick"}
    today_et = now_et().date().isoformat()

    apicks = board.get("aPicks", []) or board.get("a_picks", []) or []
    added = 0
    skipped_existing = 0
    skipped_filter = 0
    skipped_date = 0

    lines = [
        "ASTRODDS 134 SYNC CLEAN MONEYLINE PICKS CSV",
        "=" * 60,
        f"Generated ET: {now_et().isoformat()}",
        f"Board JSON: {BOARD_JSON}",
        f"Clean CSV: {CLEAN_CSV}",
        f"A PICK board candidates: {len(apicks)}",
        "",
    ]

    for p in apicks:
        game = str(p.get("game", "")).strip()
        pick = str(p.get("pick", "")).strip()
        date_raw = p.get("date", "")
        local_date = parse_iso_to_et_date(date_raw)

        model = norm_prob(p.get("model", p.get("modelProb", p.get("confidence", 0))))
        edge = norm_prob(p.get("edge", p.get("valueEdge", 0)))
        market = p.get("market", "")

        if local_date != today_et:
            skipped_date += 1
            lines.append(f"SKIP DATE | {local_date} | {pick} | {game}")
            continue

        if model >= 0.65 and edge >= 0.15:
            grade = "A+"
        elif model >= 0.62 and edge >= 0.12:
            grade = "A"
        else:
            skipped_filter += 1
            lines.append(f"SKIP FILTER | {pick} | {game} | model={model:.2f} edge={edge:.2f}")
            continue

        new_row = {
            "date": local_date,
            "game": game,
            "pick": pick,
            "result": "pending",
            "model": pct_str(model),
            "edge": pct_str(edge),
            "stake": "5%",
            "status": "clean_apick",
            "grade": grade,
            "market": str(market),
            "final_score": "",
            "resolved_at": "",
            "notes": f"Auto-added from Moneyline Telegram scan. Grade={grade}.",
        }

        key = row_key(new_row)
        if key in existing:
            skipped_existing += 1
            lines.append(f"SKIP EXISTING | {grade} | {pick} | {game}")
            continue

        rows.append(new_row)
        existing.add(key)
        added += 1
        lines.append(f"ADDED | {grade} | {pick} | {game} | model={model:.2%} edge={edge:.2%}")

    write_csv_rows(rows)

    lines.extend([
        "",
        "Summary:",
        f"- Added pending clean picks: {added}",
        f"- Skipped existing: {skipped_existing}",
        f"- Skipped filter: {skipped_filter}",
        f"- Skipped date: {skipped_date}",
        "",
        "Rule: sync only. No Telegram send. No betting automation.",
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

