from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
ACTION_JSON = ASTRO / "ASTRODDS-moneyline-actionable-today-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-partner-style-top6-moneyline-latest.json"
REPORT = REPORTS / "258_partner_style_top6_moneyline_board_report.txt"

def fnum(v, default=None):
    if v is None:
        return default
    try:
        s = str(v).strip().replace(",", ".").replace("%", "").replace("+", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def grade_from_edge(edge):
    if edge is None:
        return "NA"
    if edge >= 12:
        return "A"
    if edge >= 8:
        return "B+"
    if edge >= 5:
        return "B"
    if edge >= 3:
        return "C+"
    if edge >= 2:
        return "C"
    if edge >= 1:
        return "D"
    return "PASS"

def action_from_edge(edge):
    if edge is None:
        return "No Price"
    if edge >= 5:
        return "Buy"
    if edge >= 2:
        return "Lean"
    if edge >= 0.5:
        return "Pass/Lean"
    return "Pass"

def official_tier(edge):
    if edge is None:
        return "NO_PRICE"
    if edge >= 12:
        return "A_PICK"
    if edge >= 8:
        return "VALUE_LEAN"
    if edge >= 5:
        return "ACTION_LEAN"
    if edge >= 2:
        return "CLIENT_LEAN"
    if edge >= 0.5:
        return "CLIENT_PASS_LEAN"
    return "NO_BET"

def is_open_status(s):
    x = str(s or "").lower()
    return any(t in x for t in ["scheduled", "pre-game", "pregame", "warmup", "preview"])

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    board = load(BOARD_JSON)
    action = load(ACTION_JSON)
    rows = board.get("moneylineBoard", [])

    cards = []
    no_price = []

    for r in rows:
        price = fnum(r.get("price"), None)
        model = fnum(r.get("modelProbability"), None)
        status = r.get("liveMlbStatus") or r.get("mlbStatus") or ""

        if price is None or model is None:
            card = {
                "pick": r.get("pick"),
                "game": r.get("game"),
                "pm": price,
                "fair": model,
                "edgePct": None,
                "grade": "NA",
                "clientAction": "No Price",
                "officialTier": "NO_PRICE",
                "status": status,
                "liveMlbStatus": status,
                "reason": "Missing price or model. Shown only as incomplete, never official.",
                "priceSourceMode": r.get("priceSourceMode", ""),
            }
            no_price.append(card)
            continue

        edge = round((model - price) * 100.0, 2)

        # Partner style shows small edges too, but still only open games.
        if not is_open_status(status):
            continue

        card = {
            "pick": r.get("pick"),
            "game": r.get("game"),
            "pm": round(price * 100, 2),
            "fair": round(model * 100, 2),
            "price": price,
            "modelProbability": model,
            "edgePct": edge,
            "grade": grade_from_edge(edge),
            "clientAction": action_from_edge(edge),
            "officialTier": official_tier(edge),
            "status": status,
            "liveMlbStatus": status,
            "suggestedStake": (
                "5% max bankroll" if edge >= 12 else
                "1-2% max bankroll" if edge >= 8 else
                "0.5-1% max bankroll" if edge >= 5 else
                "dashboard only"
            ),
            "reason": f"PM {round(price*100,2)}% vs Fair {round(model*100,2)}% = edge {edge}%.",
            "priceSourceMode": r.get("priceSourceMode", ""),
            "priceSourceFile": r.get("priceSourceFile", ""),
            "modelSourceFile": r.get("modelSourceFile", ""),
        }
        cards.append(card)

    # Top 6 partner style: show best positive edges, including small leans.
    cards_sorted = sorted(cards, key=lambda x: x.get("edgePct", -999), reverse=True)
    top6 = cards_sorted[:6]
    for i, c in enumerate(top6, 1):
        c["rank"] = i

    official = [c for c in cards_sorted if c["officialTier"] in ["A_PICK", "VALUE_LEAN", "ACTION_LEAN"]]
    for i, c in enumerate(official, 1):
        c["officialRank"] = i

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputRows": len(rows),
        "scoredRows": len(cards),
        "missingRows": len(no_price),
        "top6Rows": len(top6),
        "officialRows": len(official),
        "top6ValidatedPicks": top6,
        "officialMoneyline": official,
        "missingPriceOrModel": no_price,
        "rule": "Partner-style Top 6 is a dashboard ranking. Official bets remain A_PICK/VALUE_LEAN/ACTION_LEAN only.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 258 PARTNER STYLE TOP 6 MONEYLINE BOARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Input rows: {out['inputRows']}",
        f"Scored rows: {out['scoredRows']}",
        f"Missing price/model rows: {out['missingRows']}",
        f"Top 6 rows: {out['top6Rows']}",
        f"Official rows: {out['officialRows']}",
        "",
        "TOP 6 VALIDATED PICKS STYLE:",
    ]

    if not top6:
        lines.append("- none")
    else:
        for c in top6:
            lines.append(
                f"- #{c['rank']} | {c['pick']} | {c['game']} | Edge={c['edgePct']}% | "
                f"Grade={c['grade']} | PM={c['pm']}% | Fair={c['fair']}% | Action={c['clientAction']} | "
                f"OfficialTier={c['officialTier']} | Stake={c['suggestedStake']}"
            )

    lines += ["", "OFFICIAL BET BOARD:"]
    if not official:
        lines.append("- none")
    else:
        for c in official:
            lines.append(
                f"- #{c['officialRank']} | {c['officialTier']} | {c['pick']} | {c['game']} | "
                f"price={c['price']} | model={c['modelProbability']} | edge={c['edgePct']}% | stake={c['suggestedStake']}"
            )

    lines += ["", "MISSING PRICE/MODEL PREVIEW:"]
    for c in no_price[:20]:
        lines.append(f"- {c['pick']} | {c['game']} | price={c['pm']} | model={c['fair']} | status={c['status']}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: Top 6 board is not the same as official bankroll picks."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
