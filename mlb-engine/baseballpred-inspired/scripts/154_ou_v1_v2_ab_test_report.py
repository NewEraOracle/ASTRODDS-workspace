from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

AB_CSV = ASTRO / "ASTRODDS-ou-v1-v2-ab-test-record.csv"
REPORT = REPORTS / "154_ou_v1_v2_ab_test_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-ou-v1-v2-ab-test-summary-latest.json"

ET = ZoneInfo("America/New_York")

def read_rows():
    if not AB_CSV.exists():
        return []
    with AB_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def summarize(rows, bucket):
    rs = [r for r in rows if r.get("bucket") == bucket]
    wins = sum(1 for r in rs if str(r.get("result","")).lower() == "win")
    losses = sum(1 for r in rs if str(r.get("result","")).lower() == "loss")
    pushes = sum(1 for r in rs if str(r.get("result","")).lower() == "push")
    pending = sum(1 for r in rs if str(r.get("result","")).lower() in ("pending", "", "tbd"))
    resolved = wins + losses
    win_rate = (100*wins/resolved) if resolved else 0.0
    return {
        "bucket": bucket,
        "rows": len(rs),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "pending": pending,
        "winRate": round(win_rate, 1),
    }

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    rows = read_rows()
    buckets = ["V1_LIVE_OU_A_PLUS", "V2_A_PLUS_PAPER", "V2_REVIEW"]
    summaries = [summarize(rows, b) for b in buckets]

    out = {
        "generatedAt": datetime.now(ET).isoformat(),
        "mode": "paper_ab_test_report",
        "csv": str(AB_CSV),
        "summaries": summaries,
        "decisionRule": "Do not replace live 136 until V2_A_PLUS_PAPER beats V1_LIVE_OU_A_PLUS on enough resolved picks.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 154 O/U V1 VS V2 A/B TEST REPORT",
        "=" * 64,
        f"Generated ET: {out['generatedAt']}",
        f"CSV: {AB_CSV}",
        "",
        "Summary:",
    ]
    for s in summaries:
        lines.append(
            f"- {s['bucket']}: {s['wins']}-{s['losses']} | "
            f"WinRate={s['winRate']}% | Push={s['pushes']} | Pending={s['pending']} | Rows={s['rows']}"
        )

    lines += [
        "",
        "Rows:",
    ]
    for r in rows[-30:]:
        lines.append(
            f"- {r.get('date')} | {r.get('bucket')} | {r.get('result')} | "
            f"{r.get('pick')} | {r.get('game')} | total={r.get('total_runs')} line={r.get('line')}"
        )

    lines += [
        "",
        "Decision:",
        "- Keep live 136 unchanged until V2_A_PLUS_PAPER clearly outperforms V1 live O/U A+.",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
