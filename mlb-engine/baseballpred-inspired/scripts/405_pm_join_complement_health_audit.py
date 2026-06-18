from pathlib import Path
from datetime import datetime
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
TOP6 = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
ACTION = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
REPORT = REPORTS / "405_pm_join_complement_health_audit_report.txt"

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
        s = str(v).replace(",", ".").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def main():
    board = load(BOARD)
    top6 = load(TOP6)
    action = load(ACTION)
    rows = board.get("moneylineBoard", [])

    rows_with_price = sum(1 for r in rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in rows if fnum(r.get("currentEdgePct")) is not None)
    positive = [r for r in rows if fnum(r.get("currentEdgePct"), -999) >= 0.5]

    issues = []
    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r.get("game","")), []).append(r)

    for game, group in by_game.items():
        if len(group) == 2:
            ps = [fnum(x.get("price")) for x in group]
            ms = [fnum(x.get("modelProbability")) for x in group]
            if all(p is not None for p in ps):
                total = sum(ps)
                if total < 0.90 or total > 1.15:
                    issues.append(f"PM total suspicious {total:.3f}: {group[0].get('game')}")
            if all(m is not None for m in ms):
                total_m = sum(ms)
                if total_m < 0.98 or total_m > 1.02:
                    issues.append(f"Fair total suspicious {total_m:.3f}: {group[0].get('game')}")

    angels = [r for r in rows if "Angels" in str(r.get("pick")) or "Athletics" in str(r.get("pick"))]

    if rows_with_price == len(rows) and rows_with_model == len(rows) and rows_with_edge == len(rows) and not issues:
        overall = "OK_PM_COMPLETE"
    elif rows_with_price == len(rows):
        overall = "PM_COMPLETE_WITH_WARNINGS"
    else:
        overall = "PM_INCOMPLETE"

    lines = [
        "ASTRODDS 405 PM JOIN COMPLEMENT HEALTH AUDIT",
        "=" * 72,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"Overall: {overall}",
        f"Rows: {len(rows)}",
        f"Rows with PM/price: {rows_with_price}",
        f"Rows with Fair/model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Positive edge rows >= 0.5%: {len(positive)}",
        f"Issues: {len(issues)}",
        f"Actionable rows: {action.get('actionableRows','unknown')}",
        f"Positive top6 rows: {len(top6.get('top6ValidatedPicks', []) or [])}",
        "",
        "Angels/Athletics check:",
    ]

    for r in angels:
        lines.append(f"- {r.get('pick')} | PM={round(fnum(r.get('price'))*100,2) if fnum(r.get('price')) is not None else None}% | Fair={round(fnum(r.get('modelProbability'))*100,2) if fnum(r.get('modelProbability')) is not None else None}% | Edge={r.get('currentEdgePct')}% | mode={r.get('priceSourceMode')}")

    lines += ["", "Positive Top Picks:"]
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
            lines.append(f"- {r.get('actionStatus')} | {r.get('pick')} | edge={r.get('currentEdgePct')} | stake={r.get('suggestedStake')}")
    else:
        lines.append("- none")

    if issues:
        lines += ["", "Issues:"]
        for i in issues:
            lines.append(f"- {i}")

    lines += ["", "Rule: if PM complete and Angels positive, board now matches partner structure more closely."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()


