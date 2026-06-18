from pathlib import Path
from datetime import datetime
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
ACTION = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
TOP6 = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
REPORT = REPORTS / "402_market_pm_join_health_audit_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def fnum(v):
    try:
        if v is None:
            return None
        s = str(v).replace(",", ".").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def main():
    board = load(BOARD)
    rows = board.get("moneylineBoard", [])
    action = load(ACTION)
    top6 = load(TOP6)

    rows_with_price = sum(1 for r in rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in rows if fnum(r.get("currentEdgePct")) is not None)

    issues = []
    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r.get("game", "")), []).append(r)

    for game, group in by_game.items():
        if len(group) == 2:
            ps = [fnum(r.get("price")) for r in group]
            ms = [fnum(r.get("modelProbability")) for r in group]
            if all(p is not None for p in ps):
                total = sum(ps)
                if total < 0.90 or total > 1.15:
                    issues.append(f"PM total suspicious {total:.3f}: {group[0].get('game')}")
            if all(m is not None for m in ms):
                total = sum(ms)
                if total < 0.98 or total > 1.02:
                    issues.append(f"Fair total suspicious {total:.3f}: {group[0].get('game')}")

    if rows_with_price == len(rows) and rows_with_model == len(rows) and rows_with_edge == len(rows) and not issues:
        overall = "OK_PM_FAIR_FULL_JOIN"
    elif rows_with_price == len(rows):
        overall = "PM_FULL_JOIN_WITH_WARNINGS"
    else:
        overall = "PM_STILL_INCOMPLETE"

    lines = [
        "ASTRODDS 402 MARKET PM JOIN HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Rows: {len(rows)}",
        f"Rows with PM/price: {rows_with_price}",
        f"Rows with Fair/model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Issues: {len(issues)}",
        f"Actionable rows: {action.get('actionableRows', 'unknown')}",
        f"Positive top6 rows: {len(top6.get('top6ValidatedPicks', []) or [])}",
        "",
        "Positive top6:",
    ]

    cards = top6.get("top6ValidatedPicks", []) or []
    if cards:
        for c in cards:
            lines.append(f"- #{c.get('rank')} | {c.get('pick')} | Edge={c.get('edgePct')}% | PM={c.get('pm')}% | Fair={c.get('fair')}% | Action={c.get('clientAction')} | Official={c.get('officialTier')}")
    else:
        lines.append("- none")

    lines += ["", "Official actionable:"]
    acts = action.get("actionableMoneyline", []) or []
    if acts:
        for r in acts:
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | {r.get('game')} | price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct')} | stake={r.get('suggestedStake')}")
    else:
        lines.append("- none")

    if issues:
        lines += ["", "Issues:"]
        for i in issues:
            lines.append(f"- {i}")

    lines += ["", "Rule: 18/18 PM + 18/18 Fair means source join is finally complete."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
