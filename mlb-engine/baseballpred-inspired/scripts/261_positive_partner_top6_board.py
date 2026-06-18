from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-positive-partner-top6-moneyline-latest.json"
REPORT = REPORTS / "261_positive_partner_top6_board_report.txt"

def fnum(v, default=None):
    if v is None:
        return default
    try:
        s = str(v).replace(",", ".").replace("%", "").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def grade(edge):
    if edge is None:
        return "NA"
    if edge >= 12:
        return "A"
    if edge >= 8:
        return "B+"
    if edge >= 5:
        return "B"
    if edge >= 3:
        return "B"
    if edge >= 2:
        return "C"
    if edge >= 1:
        return "D"
    if edge >= 0.5:
        return "D"
    return "PASS"

def action(edge):
    if edge is None:
        return "No Price"
    if edge >= 3:
        return "Buy"
    if edge >= 1:
        return "Lean"
    if edge >= 0.5:
        return "Pass/Lean"
    return "Pass"

def official(edge):
    if edge is None:
        return "NO_PRICE"
    if edge >= 12:
        return "A_PICK"
    if edge >= 8:
        return "VALUE_LEAN"
    if edge >= 5:
        return "ACTION_LEAN"
    if edge >= 0.5:
        return "CLIENT_LEAN"
    return "NO_BET"

def is_open(s):
    x = str(s or "").lower()
    return any(t in x for t in ["scheduled", "pre-game", "pregame", "warmup", "preview"])

def main():
    data = load(BOARD_JSON)
    rows = data.get("moneylineBoard", [])

    scored = []
    missing = []
    negative = []

    for r in rows:
        p = fnum(r.get("price"))
        m = fnum(r.get("modelProbability"))
        status = r.get("liveMlbStatus") or r.get("mlbStatus") or ""

        if not is_open(status):
            continue

        if p is None or m is None:
            missing.append({
                "pick": r.get("pick"),
                "game": r.get("game"),
                "price": p,
                "modelProbability": m,
                "status": status,
                "reason": "Missing price or model.",
            })
            continue

        e = round((m - p) * 100.0, 2)
        card = {
            "pick": r.get("pick"),
            "game": r.get("game"),
            "price": p,
            "modelProbability": m,
            "pm": round(p * 100, 2),
            "fair": round(m * 100, 2),
            "edgePct": e,
            "grade": grade(e),
            "clientAction": action(e),
            "officialTier": official(e),
            "suggestedStake": (
                "5% max bankroll" if e >= 12 else
                "1-2% max bankroll" if e >= 8 else
                "0.5-1% max bankroll" if e >= 5 else
                "dashboard only"
            ),
            "liveMlbStatus": status,
            "priceSourceMode": r.get("priceSourceMode", ""),
            "priceSourceFile": r.get("priceSourceFile", ""),
            "modelSourceFile": r.get("modelSourceFile", ""),
        }
        if e >= 0.5:
            scored.append(card)
        else:
            negative.append(card)

    scored.sort(key=lambda x: x["edgePct"], reverse=True)
    top6 = scored[:6]
    for i, c in enumerate(top6, 1):
        c["rank"] = i

    official_rows = [c for c in scored if c["officialTier"] in ["A_PICK", "VALUE_LEAN", "ACTION_LEAN"]]
    for i, c in enumerate(official_rows, 1):
        c["officialRank"] = i

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputRows": len(rows),
        "positiveScoredRows": len(scored),
        "negativeOrPassRows": len(negative),
        "missingRows": len(missing),
        "top6ValidatedPicks": top6,
        "officialMoneyline": official_rows,
        "negativeOrPass": negative,
        "missingPriceOrModel": missing,
        "rule": "Top 6 only includes positive edges >= 0.5%. Negative/pass rows are not Top 6.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 261 POSITIVE PARTNER STYLE TOP 6 BOARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Input rows: {out['inputRows']}",
        f"Positive scored rows: {out['positiveScoredRows']}",
        f"Negative/pass rows: {out['negativeOrPassRows']}",
        f"Missing price/model rows: {out['missingRows']}",
        "",
        "TOP POSITIVE VALIDATED PICKS:",
    ]
    if top6:
        for c in top6:
            lines.append(f"- #{c['rank']} | {c['pick']} | {c['game']} | Edge={c['edgePct']}% | Grade={c['grade']} | PM={c['pm']}% | Fair={c['fair']}% | Action={c['clientAction']} | Official={c['officialTier']} | Stake={c['suggestedStake']}")
    else:
        lines.append("- none")

    lines += ["", "OFFICIAL BET BOARD:"]
    if official_rows:
        for c in official_rows:
            lines.append(f"- {c['officialTier']} | {c['pick']} | {c['game']} | edge={c['edgePct']}% | stake={c['suggestedStake']}")
    else:
        lines.append("- none")

    lines += ["", "NEGATIVE/PASS PREVIEW:"]
    for c in negative[:20]:
        lines.append(f"- {c['pick']} | {c['game']} | edge={c['edgePct']}% | PM={c['pm']}% | Fair={c['fair']}%")

    lines += ["", "MISSING PREVIEW:"]
    for c in missing[:20]:
        lines.append(f"- {c['pick']} | {c['game']} | price={c['price']} | model={c['modelProbability']}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: partner style board should not rank negative edges as top picks."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
