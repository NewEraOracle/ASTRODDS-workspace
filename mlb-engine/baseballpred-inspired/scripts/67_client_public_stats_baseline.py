from pathlib import Path
import json
import csv
from datetime import datetime, timezone
import shutil

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENGINE_LEDGER = ROOT / ".astrodds" / "ASTRODDS-engine-signal-ledger.json"
PROOF_JSON = ROOT / "public" / "astrodds-proof-log.json"

CLIENT_LEDGER = ROOT / ".astrodds" / "ASTRODDS-client-performance-ledger.json"
CLIENT_CSV = ROOT / ".astrodds" / "ASTRODDS-client-performance-ledger.csv"
CLIENT_PUBLIC_JSON = ROOT / "public" / "astrodds-client-performance.json"
CLIENT_PUBLIC_CSV = ROOT / "public" / "astrodds-client-performance.csv"

ARCHIVE_DIR = ROOT / ".astrodds" / "archive"
REPORT = BASE / "reports" / "67_client_public_stats_baseline_report.txt"
POLICY = BASE / "models" / "ASTRODDS_CLIENT_PUBLIC_STATS_POLICY.json"

BASELINE_GAME_KEYWORDS = ["tampa bay rays", "los angeles angels"]
BASELINE_PICK = "los angeles angels"
BASELINE_RESULT = "win"

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

def is_angels_win(row):
    game = str(row.get("game") or "").lower()
    pick = str(row.get("pick") or "").lower()
    result = str(row.get("result") or "").lower()
    return all(k in game for k in BASELINE_GAME_KEYWORDS) and pick == BASELINE_PICK and result == BASELINE_RESULT

def normalize_client_row(row):
    out = dict(row)
    out["clientTrackingStatus"] = "included_public_client_performance"
    out["clientTrackingReason"] = "baseline_start_angels_win"
    out["clientTrackingStartedAt"] = datetime.now(timezone.utc).isoformat()
    out["publicStatsPolicy"] = "client_public_stats_only"
    out["paperOnly"] = True
    out["realMoneyAutomation"] = False
    return out

def summarize(rows):
    wins = sum(1 for r in rows if str(r.get("result", "")).lower() == "win")
    losses = sum(1 for r in rows if str(r.get("result", "")).lower() == "loss")
    pending = sum(1 for r in rows if str(r.get("result", "pending")).lower() not in ["win", "loss", "push", "void"])
    resolved = wins + losses
    win_rate = round((wins / resolved) * 100, 2) if resolved else None
    units = round(sum(fnum(r.get("paperProfitUnits")) for r in rows), 3)
    return {
        "totalClientTrackedSignals": len(rows),
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "resolved": resolved,
        "winRatePct": win_rate,
        "paperUnits": units,
    }

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date", "game", "pick", "finalEngineDecision", "finalGrade", "result",
        "winner", "awayRuns", "homeRuns", "paperProfitUnits",
        "clientTrackingStatus", "clientTrackingReason", "paperOnly"
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})

def main():
    generated = datetime.now(timezone.utc).isoformat()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    archived = []
    for p in [ENGINE_LEDGER, PROOF_JSON, CLIENT_LEDGER, CLIENT_PUBLIC_JSON]:
        if p.exists():
            target = ARCHIVE_DIR / f"{p.name}.backup-before-client-baseline-{stamp}"
            shutil.copy2(p, target)
            archived.append(str(target))

    engine_rows = read_json(ENGINE_LEDGER, [])
    if not isinstance(engine_rows, list):
        engine_rows = []

    baseline_rows = [normalize_client_row(r) for r in engine_rows if isinstance(r, dict) and is_angels_win(r)]

    existing = read_json(CLIENT_LEDGER, [])
    if not isinstance(existing, list):
        existing = []

    merged = []
    seen = set()
    for r in existing + baseline_rows:
        if not isinstance(r, dict) or not is_angels_win(r):
            continue
        key = f"{r.get('date')}|{r.get('game')}|{r.get('pick')}|{r.get('result')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)

    summary = summarize(merged)

    public_data = {
        "generatedAt": generated,
        "mode": "client_public_performance_baseline",
        "trackingStart": "Angels win baseline",
        "summary": summary,
        "rows": merged,
        "excludedNote": "Previous review/watch/manual test rows are archived and excluded from client public stats.",
        "paperOnly": True,
        "realMoneyAutomation": False,
    }

    write_json(CLIENT_LEDGER, merged)
    write_csv(CLIENT_CSV, merged)
    write_json(CLIENT_PUBLIC_JSON, public_data)
    write_csv(CLIENT_PUBLIC_CSV, merged)

    policy = {
        "version": "ASTRODDS_CLIENT_PUBLIC_STATS_POLICY_V1",
        "createdAt": generated,
        "status": "OK" if merged else "REVIEW_NEEDED_NO_BASELINE_FOUND",
        "publicStatsRule": "Client/investor public stats start from the real Angels win baseline. Previous review/watch/manual test rows are archived and excluded from public stats.",
        "includedBaseline": {
            "gameContains": BASELINE_GAME_KEYWORDS,
            "pick": BASELINE_PICK,
            "result": BASELINE_RESULT,
        },
        "outputs": {
            "clientLedgerJson": str(CLIENT_LEDGER),
            "clientLedgerCsv": str(CLIENT_CSV),
            "publicJson": str(CLIENT_PUBLIC_JSON),
            "publicCsv": str(CLIENT_PUBLIC_CSV),
        },
        "paperOnly": True,
        "realMoneyAutomation": False,
    }
    write_json(POLICY, policy)

    lines = []
    lines.append("ASTRODDS 67 CLIENT PUBLIC STATS BASELINE REPORT")
    lines.append("=" * 58)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {policy['status']}")
    lines.append("")
    lines.append("Action:")
    lines.append("- Public/client stats now start from the real Angels win baseline.")
    lines.append("- Old mixed review/watch/manual rows were archived, not destroyed.")
    lines.append("")
    lines.append("Baseline summary:")
    lines.append(f"- Signals: {summary['totalClientTrackedSignals']}")
    lines.append(f"- Wins: {summary['wins']}")
    lines.append(f"- Losses: {summary['losses']}")
    lines.append(f"- Pending: {summary['pending']}")
    lines.append(f"- Win rate: {summary['winRatePct']}%")
    lines.append(f"- Paper units: {summary['paperUnits']}u")
    lines.append("")
    lines.append("Included rows:")
    for r in merged:
        lines.append(f"- {r.get('date')} | {r.get('game')} | Pick: {r.get('pick')} | Result: {r.get('result')} | Units: {r.get('paperProfitUnits')}")
    lines.append("")
    lines.append("Archived files:")
    for a in archived:
        lines.append(f"- {a}")
    lines.append("")
    lines.append(f"Client ledger JSON: {CLIENT_LEDGER}")
    lines.append(f"Client ledger CSV: {CLIENT_CSV}")
    lines.append(f"Public client JSON: {CLIENT_PUBLIC_JSON}")
    lines.append(f"Public client CSV: {CLIENT_PUBLIC_CSV}")
    lines.append(f"Policy JSON: {POLICY}")
    lines.append("")
    lines.append("Rule: client public stats baseline only. No odds scan. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()