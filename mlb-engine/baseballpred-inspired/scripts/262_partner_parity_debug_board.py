from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-partner-parity-debug-latest.json"
REPORT = REPORTS / "262_partner_parity_debug_board_report.txt"

PARTNER_PICKS = {
    "Cleveland Guardians": {"partnerPM": 41.5, "partnerFair": 45.7, "partnerEdge": 4.2},
    "Los Angeles Angels": {"partnerPM": 44.5, "partnerFair": 48.3, "partnerEdge": 3.8},
    "Chicago White Sox": {"partnerPM": 41.5, "partnerFair": 43.5, "partnerEdge": 2.0},
    "San Francisco Giants": {"partnerPM": 42.5, "partnerFair": 43.6, "partnerEdge": 1.1},
    "Baltimore Orioles": {"partnerPM": 42.5, "partnerFair": 44.9, "partnerEdge": 2.4},
    "St. Louis Cardinals": {"partnerPM": 48.5, "partnerFair": 49.1, "partnerEdge": 0.6},
}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

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

def main():
    rows = load(BOARD_JSON).get("moneylineBoard", [])
    by_pick = {norm(r.get("pick")): r for r in rows}

    comparisons = []
    for pick, partner in PARTNER_PICKS.items():
        r = by_pick.get(norm(pick), {})
        price = fnum(r.get("price"))
        model = fnum(r.get("modelProbability"))
        edge = round((model - price) * 100, 2) if price is not None and model is not None else None

        comparisons.append({
            "pick": pick,
            "game": r.get("game", ""),
            "ourPM": round(price * 100, 2) if price is not None else None,
            "ourFair": round(model * 100, 2) if model is not None else None,
            "ourEdge": edge,
            "partnerPM": partner["partnerPM"],
            "partnerFair": partner["partnerFair"],
            "partnerEdge": partner["partnerEdge"],
            "pmDiff": round((round(price * 100, 2) if price is not None else 0) - partner["partnerPM"], 2) if price is not None else None,
            "fairDiff": round((round(model * 100, 2) if model is not None else 0) - partner["partnerFair"], 2) if model is not None else None,
            "edgeDiff": round(edge - partner["partnerEdge"], 2) if edge is not None else None,
            "priceSourceMode": r.get("priceSourceMode", ""),
            "priceSourceFile": r.get("priceSourceFile", ""),
            "modelSourceFile": r.get("modelSourceFile", ""),
            "liveMlbStatus": r.get("liveMlbStatus", ""),
        })

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "comparisons": comparisons,
        "rule": "Compare our PM/Fair/Edge against partner screenshot. Large diffs mean model/price source parity is not matched.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 262 PARTNER PARITY DEBUG BOARD",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Comparison vs partner screenshot:",
    ]
    for c in comparisons:
        lines.append(
            f"- {c['pick']} | game={c['game']} | OUR PM={c['ourPM']} Fair={c['ourFair']} Edge={c['ourEdge']} | "
            f"PARTNER PM={c['partnerPM']} Fair={c['partnerFair']} Edge={c['partnerEdge']} | "
            f"Diff PM={c['pmDiff']} Fair={c['fairDiff']} Edge={c['edgeDiff']} | priceMode={c['priceSourceMode']}"
        )

    lines += ["", f"JSON: {OUT_JSON}", "Rule: parity mismatch is expected until PM/Fair sources match partner exactly."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
