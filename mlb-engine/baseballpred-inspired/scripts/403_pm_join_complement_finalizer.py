from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-403-pm-join-complement-finalizer-latest.json"
REPORT = REPORTS / "403_pm_join_complement_finalizer_report.txt"

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

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
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    by_game = {}
    for r in rows:
        by_game.setdefault(norm(r.get("game", "")), []).append(r)

    filled = 0
    warnings = []

    for game, group in by_game.items():
        if len(group) != 2:
            warnings.append(f"Non-binary group skipped: {game} rows={len(group)}")
            continue

        a, b = group
        pa = fnum(a.get("price"))
        pb = fnum(b.get("price"))

        if pa is not None and pb is None:
            b["price"] = round(max(0.01, min(0.99, 1.0 - pa)), 6)
            b["priceSourceFile"] = "pm_exact_join_complement_from_opponent"
            b["priceSourceColumn"] = a.get("pick", "")
            b["priceSourceMode"] = "binary_pm_complement_after_exact_join"
            b["opponentPricePick"] = a.get("pick", "")
            b["opponentPrice"] = pa
            filled += 1

        elif pb is not None and pa is None:
            a["price"] = round(max(0.01, min(0.99, 1.0 - pb)), 6)
            a["priceSourceFile"] = "pm_exact_join_complement_from_opponent"
            a["priceSourceColumn"] = b.get("pick", "")
            a["priceSourceMode"] = "binary_pm_complement_after_exact_join"
            a["opponentPricePick"] = b.get("pick", "")
            a["opponentPrice"] = pb
            filled += 1

        elif pa is not None and pb is not None:
            total = pa + pb
            if total < 0.90 or total > 1.15:
                warnings.append(f"Suspicious PM total {total:.3f}: {a.get('game')}")

    for r in rows:
        price = fnum(r.get("price"))
        model = fnum(r.get("modelProbability"))
        if price is not None and model is not None:
            r["currentEdgePct"] = round((model - price) * 100.0, 2)
            r["edgePct"] = r["currentEdgePct"]
        else:
            r["currentEdgePct"] = None
            r["edgePct"] = None

    rows_with_price = sum(1 for r in rows if fnum(r.get("price")) is not None)
    rows_with_model = sum(1 for r in rows if fnum(r.get("modelProbability")) is not None)
    rows_with_edge = sum(1 for r in rows if fnum(r.get("currentEdgePct")) is not None)
    positive = [r for r in rows if fnum(r.get("currentEdgePct"), -999) >= 0.5]

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "rowsWithPrice": rows_with_price,
        "rowsWithModel": rows_with_model,
        "rowsWithEdge": rows_with_edge,
        "complementFilled": filled,
        "positiveRows": len(positive),
        "warnings": warnings,
        "moneylineBoard": rows,
        "rule": "After exact team PM join, fill the one missing side in a binary moneyline with 1 - opponent PM.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({"generatedAt": out["generatedAt"], "moneylineRows": len(rows), "moneylineBoard": rows, "rule": out["rule"]}, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 403 PM JOIN COMPLEMENT FINALIZER",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows: {len(rows)}",
        f"Rows with PM/price: {rows_with_price}",
        f"Rows with Fair/model: {rows_with_model}",
        f"Rows with edge: {rows_with_edge}",
        f"Complement filled: {filled}",
        f"Positive edge rows >= 0.5%: {len(positive)}",
        f"Warnings: {len(warnings)}",
        "",
        "Board:",
    ]
    for r in rows:
        p = fnum(r.get("price"))
        m = fnum(r.get("modelProbability"))
        lines.append(
            f"- {r.get('pick')} | {r.get('game')} | PM={round(p*100,2) if p is not None else None}% | "
            f"Fair={round(m*100,2) if m is not None else None}% | Edge={r.get('currentEdgePct')}% | "
            f"status={r.get('liveMlbStatus')} | mode={r.get('priceSourceMode','')}"
        )

    if warnings:
        lines += ["", "Warnings:"]
        for w in warnings:
            lines.append(f"- {w}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: this should complete Angels PM from Athletics PM safely."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
