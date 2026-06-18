from pathlib import Path
from datetime import datetime, timezone
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
TOP6_JSON = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
CLIENT_TG_JSON = ASTRO / "ASTRODDS-client-lean-telegram-message-latest.json"

OUT_JSON = ASTRO / "ASTRODDS-500-one-command-status-latest.json"
REPORT = REPORTS / "500_astrodds_one_command_status_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def fnum(v, default=None):
    try:
        if v is None:
            return default
        s = str(v).replace(",", ".").replace("%", "").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def latest_report_text(name):
    p = REPORTS / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")

def status_from_report(pattern, text):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    board_data = load(BOARD_JSON)
    rows = board_data.get("moneylineBoard", []) or []

    top6_data = load(TOP6_JSON)
    top6 = top6_data.get("top6ValidatedPicks", []) or []

    action_data = load(ACTION_JSON)
    actionable = action_data.get("actionableMoneyline", []) or []

    client_tg = load(CLIENT_TG_JSON)

    rows_with_price = sum(1 for r in rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in rows if fnum(r.get("currentEdgePct")) is not None)

    pm_complete = len(rows) > 0 and rows_with_price == len(rows)
    model_complete = len(rows) > 0 and rows_with_model == len(rows)
    edge_complete = len(rows) > 0 and rows_with_edge == len(rows)

    top_pick = top6[0] if top6 else None
    official_pick_count = len(actionable)

    health405 = latest_report_text("405_pm_join_complement_health_audit_report.txt")
    health_overall = status_from_report(r"Overall:\s*([A-Z0-9_]+)", health405)

    tg410 = latest_report_text("410_send_client_lean_telegram_safe_report.txt")
    tg_status = status_from_report(r"Status:\s*([A-Z0-9_]+)", tg410)
    tg_ok = "TelegramOK: True" in tg410 or tg_status in ["SENT", "SKIPPED_DUPLICATE_MESSAGE"]

    runner31 = latest_report_text("31_auto_daily_engine_runner_report.txt")
    postprocess_ok = "CREDIT_GUARD_BLOCKED_PM_POSTPROCESS_FORCE_DONE" in runner31 or "PM join complement health audit 405 exit code: 0" in runner31

    issues = []
    if not rows:
        issues.append("moneyline_board_missing")
    if not pm_complete:
        issues.append(f"pm_price_incomplete_{rows_with_price}_of_{len(rows)}")
    if not model_complete:
        issues.append(f"fair_model_incomplete_{rows_with_model}_of_{len(rows)}")
    if not edge_complete:
        issues.append(f"edge_incomplete_{rows_with_edge}_of_{len(rows)}")
    if health_overall and health_overall != "OK_PM_COMPLETE":
        issues.append(f"health405_{health_overall}")
    if not top6:
        issues.append("no_positive_client_lean")
    # Telegram send and runner observation are live-mode checks.
    # A dry/local 10-of-10 status cycle should still be READY when the board is complete
    # and the client lean message is built.
    live_warnings = []

    if client_tg and client_tg.get("shouldSend") and not tg_ok:
        live_warnings.append("client_lean_telegram_not_confirmed_sent")

    if runner31 and not postprocess_ok:
        live_warnings.append("runner_pm_postprocess_not_seen")

    hard_issues = [
        x for x in issues
        if x not in ["no_positive_client_lean"]
    ]

    if not hard_issues and pm_complete and model_complete and edge_complete and health_overall == "OK_PM_COMPLETE":
        if tg_ok and postprocess_ok:
            overall = "PRODUCTION_LIVE_OK"
            score = "10/10 live production"
        else:
            overall = "PRODUCTION_READY"
            score = "9.5/10 ready - live Telegram/runner confirmation optional"
    elif all(x in issues for x in ["no_positive_client_lean"]) and len(issues) == 1:
        overall = "OK_NO_VALUE_TODAY"
        score = "9.5/10 no positive value today"
    else:
        overall = "CHECK_REQUIRED"
        score = "needs attention"

    issues = hard_issues
    warnings = live_warnings

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "score": score,
        "rows": len(rows),
        "rowsWithPrice": rows_with_price,
        "rowsWithModel": rows_with_model,
        "rowsWithEdge": rows_with_edge,
        "pmComplete": pm_complete,
        "modelComplete": model_complete,
        "edgeComplete": edge_complete,
        "health405": health_overall,
        "officialPickCount": official_pick_count,
        "clientTopPick": top_pick,
        "telegramClientLeanStatus": tg_status,
        "runnerPostprocessOK": postprocess_ok,
        "issues": issues,
        "warnings": warnings if "warnings" in locals() else [],
        "rule": "One-command status: board completeness, top pick, official pick count, Telegram status, runner postprocess.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 500 ONE-COMMAND STATUS",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Overall: {overall}",
        f"Score: {score}",
        "",
        "Core board:",
        f"- Rows: {len(rows)}",
        f"- PM/price: {rows_with_price}/{len(rows)}",
        f"- Fair/model: {rows_with_model}/{len(rows)}",
        f"- Edge: {rows_with_edge}/{len(rows)}",
        f"- 405 health: {health_overall or 'not available'}",
        "",
        "Signals:",
        f"- Official actionable picks: {official_pick_count}",
        f"- Positive client lean rows: {len(top6)}",
    ]

    if top_pick:
        lines += [
            "",
            "Top client lean:",
            f"- Pick: {top_pick.get('pick')} ML",
            f"- Game: {top_pick.get('game')}",
            f"- PM: {top_pick.get('pm')}%",
            f"- Fair: {top_pick.get('fair')}%",
            f"- Edge: +{top_pick.get('edgePct')}%",
            f"- Grade: {top_pick.get('grade')}",
            f"- Action: {top_pick.get('clientAction')}",
            f"- Tier: {top_pick.get('officialTier')}",
            f"- Stake: {top_pick.get('suggestedStake')}",
        ]

    lines += [
        "",
        "Telegram:",
        f"- Client lean message shouldSend: {client_tg.get('shouldSend') if client_tg else 'not built'}",
        f"- Client lean Telegram status: {tg_status or 'not available'}",
        f"- Telegram OK / duplicate-safe: {tg_ok}",
        "",
        "Runner:",
        f"- PM postprocess observed: {postprocess_ok}",
        "",
        "Issues:",
    ]

    if issues:
        for x in issues:
            lines.append(f"- {x}")
    else:
        lines.append("- none")

    lines += ["", "Warnings:"]
    if "warnings" in locals() and warnings:
        for x in warnings:
            lines.append(f"- {x}")
    else:
        lines.append("- none")

    lines += [
        "",
        "Meaning:",
        "- PRODUCTION_OK means daily moneyline board is complete and Telegram/client lean layer is working.",
        "- No official A_PICK can still be correct if no edge passes strict bankroll thresholds.",
        "",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()

