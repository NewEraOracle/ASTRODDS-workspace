# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
REPORT = BASE / "reports" / "84_astrodss_final_health_audit_report.txt"

checks = []

def add(name, ok, detail=""):
    checks.append((name, bool(ok), detail))

def exists(rel):
    return (ROOT / rel).exists()

def text(rel):
    p = ROOT / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8-sig", errors="ignore")

def json_count(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return len(data) if isinstance(data, list) else None
    except Exception:
        return None

route = text("app/api/astrodds/best-bets/today/route.ts")
telegram = text("mlb-engine/baseballpred-inspired/scripts/30_telegram_final_engine_alerts.py")
runner = text("mlb-engine/baseballpred-inspired/scripts/31_auto_daily_engine_runner.ps1")

add("API timeout fallback", "GET_IMPL" in route and "recovered from upstream timeout" in route)
add("API today-only safe official picks", "isSafeTodayOfficialPick" in route and "edge >= 0.03" in route)
add("Telegram today-only filter", "is_today_game" in telegram and "row_edge >= 3" in telegram)
add("Telegram A PICK / VALUE LEAN", "A PICK" in telegram and "VALUE LEAN" in telegram)
add("Telegram blocks final games", "is_active_game" in telegram and "final" in telegram.lower())
add("Smart gate 69 exists", exists("mlb-engine/baseballpred-inspired/scripts/69_official_buy_blocker_audit.py"))
add("Smart gate 70 exists", exists("mlb-engine/baseballpred-inspired/scripts/70_soft_hard_context_gate.py"))
add("Smart gate 71 exists", exists("mlb-engine/baseballpred-inspired/scripts/71_smart_official_buy_promotion.py"))
add("Runner calls injury gate", "61_free_injury_context_gate.py" in runner)
add("Runner calls smart gate", "69_official_buy_blocker_audit.py" in runner and "70_soft_hard_context_gate.py" in runner and "71_smart_official_buy_promotion.py" in runner)
add("Runner calls Telegram final alerts", "30_telegram_final_engine_alerts.py" in runner)
add("Runner calls result tracking", "81_telegram_result_tracking.py" in runner)
add("Result tracking exists", exists("mlb-engine/baseballpred-inspired/scripts/81_telegram_result_tracking.py"))

signals_count = json_count(".astrodds/ASTRODDS-engine-final-signals-latest.json")
if signals_count is not None:
    add("Engine final signals readable", signals_count >= 0, f"rows={signals_count}")
else:
    add("Engine final signals readable", False, "missing or invalid")

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
score = round((passed / total) * 10, 1) if total else 0

lines = [
    "ASTRODDS 84 FINAL HEALTH AUDIT",
    "=" * 56,
    f"Generated UTC: {datetime.utcnow().isoformat()}Z",
    f"Score: {score}/10",
    f"Passed: {passed}/{total}",
    "",
    "Checks:",
]

for name, ok, detail in checks:
    lines.append(f"- {'OK' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))

lines += [
    "",
    "Interpretation:",
    "- 9+/10 means the public signal safety flow is production-safe for manual/paper use.",
    "- Remaining 10/10 work: improve clean market price matching and client dashboard polish.",
    "",
    "Rule: Paper/manual only. No real-money automation.",
]

REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
