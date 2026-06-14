from pathlib import Path
import json
import os
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

LEDGER = ROOT / ".astrodds" / "ASTRODDS-credit-guard-ledger.json"
REPORT = BASE / "reports" / "48_credit_guard_report.txt"

DEFAULT_MAX_DAILY_SCANS = 3
DEFAULT_MAX_MONTHLY_SCANS = 90
DEFAULT_MONTHLY_RESERVE = 20

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def env_int(name, default):
    try:
        value = os.environ.get(name)
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except Exception:
        return default

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

def same_day(value, stamp):
    return str(value)[:10] == stamp[:10]

def same_month(value, stamp):
    return str(value)[:7] == stamp[:7]

def main():
    mode = "status"
    if len(sys.argv) > 1:
        mode = sys.argv[1].strip().lower()

    stamp = now_utc()
    max_daily = env_int("ASTRODDS_MAX_DAILY_SCANS", DEFAULT_MAX_DAILY_SCANS)
    max_monthly = env_int("ASTRODDS_MAX_MONTHLY_SCANS", DEFAULT_MAX_MONTHLY_SCANS)
    monthly_reserve = env_int("ASTRODDS_MONTHLY_SCAN_RESERVE", DEFAULT_MONTHLY_RESERVE)
    effective_monthly = max(0, max_monthly - monthly_reserve)

    ledger = read_json(LEDGER, [])
    if not isinstance(ledger, list):
        ledger = []

    daily_before = [r for r in ledger if same_day(r.get("startedAt", ""), stamp)]
    monthly_before = [r for r in ledger if same_month(r.get("startedAt", ""), stamp)]

    allowed = True
    reason = "scan allowed"

    if len(daily_before) >= max_daily:
        allowed = False
        reason = f"daily scan limit reached: {len(daily_before)}/{max_daily}"

    if len(monthly_before) >= effective_monthly:
        allowed = False
        reason = f"monthly usable scan limit reached: {len(monthly_before)}/{effective_monthly}; reserve protected"

    recorded = False
    status = "STATUS_ONLY"

    if mode == "record":
        if allowed:
            ledger.append({
                "startedAt": stamp,
                "mode": "record",
                "paperOnly": True,
                "reason": reason
            })
            write_json(LEDGER, ledger)
            recorded = True
            status = "ALLOWED"
        else:
            status = "BLOCKED"

    elif mode == "status":
        status = "STATUS_ONLY"

    elif mode == "force":
        ledger.append({
            "startedAt": stamp,
            "mode": "force",
            "paperOnly": True,
            "reason": "manual force override"
        })
        write_json(LEDGER, ledger)
        recorded = True
        allowed = True
        status = "FORCED"
        reason = "manual force override"

    else:
        allowed = False
        status = "ERROR"
        reason = f"unknown mode: {mode}"

    updated = read_json(LEDGER, [])
    if not isinstance(updated, list):
        updated = []

    daily_after = [r for r in updated if same_day(r.get("startedAt", ""), stamp)]
    monthly_after = [r for r in updated if same_month(r.get("startedAt", ""), stamp)]

    lines = []
    lines.append("ASTRODDS 48 CREDIT GUARD REPORT")
    lines.append("=" * 42)
    lines.append(f"Generated UTC: {stamp}")
    lines.append("")
    lines.append(f"Mode: {mode}")
    lines.append(f"Status: {status}")
    lines.append(f"Allowed: {allowed}")
    lines.append(f"Recorded this run: {recorded}")
    lines.append(f"Reason: {reason}")
    lines.append("")
    lines.append("Limits:")
    lines.append(f"- Max daily scans: {max_daily}")
    lines.append(f"- Max monthly scans: {max_monthly}")
    lines.append(f"- Monthly reserve: {monthly_reserve}")
    lines.append(f"- Effective monthly usable scans: {effective_monthly}")
    lines.append("")
    lines.append("Usage:")
    lines.append(f"- Daily scans before: {len(daily_before)}")
    lines.append(f"- Monthly scans before: {len(monthly_before)}")
    lines.append(f"- Daily scans after: {len(daily_after)}")
    lines.append(f"- Monthly scans after: {len(monthly_after)}")
    lines.append("")
    lines.append(f"Ledger: {LEDGER}")
    lines.append("")
    lines.append("Rule: credit protection only. Paper/manual only. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

    if status == "BLOCKED":
        sys.exit(2)

    if status == "ERROR":
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
