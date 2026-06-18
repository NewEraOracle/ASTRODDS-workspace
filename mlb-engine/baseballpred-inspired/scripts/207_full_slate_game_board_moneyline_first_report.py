from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

ML_JSON = ASTRO / "ASTRODDS-moneyline-baseballpred-full-slate-fixed-latest.json"
CLEAN_JSON = ASTRO / "ASTRODDS-full-slate-game-board-clean-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-full-slate-game-board-moneyline-first-latest.json"
REPORT = REPORTS / "207_full_slate_game_board_moneyline_first_report.txt"

STATUS_ORDER = {"OFFICIAL": 0, "A_PAPER": 1, "REVIEW": 2, "WATCH": 3, "BLOCKED": 4, "NO_BET": 5}

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fnum(v, default=0):
    try:
        s = str(v).strip().replace("+", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def sort_rows(rows):
    return sorted(rows, key=lambda r: (STATUS_ORDER.get(r.get("status", "NO_BET"), 9), -fnum(r.get("baseballPredScore"), 0)))

def main():
    ml_data = load(ML_JSON)
    clean_data = load(CLEAN_JSON)

    ml_rows = ml_data.get("moneylineBoard", []) if isinstance(ml_data, dict) else []
    all_rows = clean_data.get("gameBoard", []) if isinstance(clean_data, dict) else []
    ou_rows = [r for r in all_rows if r.get("marketType") == "OU"]

    final_rows = sort_rows(ml_rows) + sort_rows(ou_rows)

    for i, r in enumerate(final_rows, 1):
        r["rank"] = i

    counts = {}
    for r in final_rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    summary = {
        "totalRows": len(final_rows),
        "moneylineRows": len(ml_rows),
        "ouRows": len(ou_rows),
        "official": counts.get("OFFICIAL", 0),
        "aPaper": counts.get("A_PAPER", 0),
        "review": counts.get("REVIEW", 0),
        "watch": counts.get("WATCH", 0),
        "blockedNoBet": counts.get("BLOCKED", 0) + counts.get("NO_BET", 0),
        "telegramEligible": sum(1 for r in final_rows if r.get("telegramEligible")),
    }

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "gameBoard": final_rows,
        "rule": "Moneyline-first dashboard board. Telegram unchanged.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 207 FULL SLATE GAME BOARD â€” MONEYLINE FIRST",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Summary:",
    ]
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "MONEYLINE FIRST BOARD:"]
    for r in final_rows:
        if r.get("marketType") != "MONEYLINE":
            continue
        lines.append(
            f"- #{r['rank']} | {r.get('status')} | {r.get('pick')} | {r.get('game')} | "
            f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('edgePct')} | "
            f"score={r.get('baseballPredScore')} | telegram={r.get('telegramEligible')}"
        )
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")

    lines += ["", "TOP O/U BOARD:"]
    for r in [x for x in final_rows if x.get("marketType") == "OU"][:30]:
        lp = r.get("line") or r.get("price") or ""
        edge = r.get("edgeRuns") or r.get("edgePct") or ""
        lines.append(
            f"- #{r['rank']} | {r.get('status')} | {r.get('pick')} | {r.get('game')} | "
            f"line={lp} | edge={edge} | score={r.get('baseballPredScore')} | telegram={r.get('telegramEligible')}"
        )
        if r.get("riskReason"):
            lines.append(f"   Risk: {r.get('riskReason')}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
