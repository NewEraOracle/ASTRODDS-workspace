from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
REPORT = REPORTS / "192_calibration_control_board_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-calibration-control-board-latest.json"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    readiness = load(ASTRO / "ASTRODDS-calibration-data-readiness-latest.json")
    hist_ml = load(ASTRO / "ASTRODDS-moneyline-historical-calibration-latest.json")
    live = load(ASTRO / "ASTRODDS-live-pick-calibration-latest.json")
    roi = load(ASTRO / "ASTRODDS-market-roi-clv-summary-latest.json")
    bpen = load(ASTRO / "ASTRODDS-bpen-whip35-exact-statsapi-latest.json")

    live_data = live.get("data", {})
    blockers = []
    actions = []

    if live_data.get("moneyline_clean", {}).get("resolved", 0) < 30:
        blockers.append("Moneyline live calibration sample < 30")
    if live_data.get("ou_clean", {}).get("resolved", 0) < 30:
        blockers.append("O/U live calibration sample < 30")
    if live_data.get("market_lines", {}).get("resolved", 0) < 30:
        blockers.append("Market ROI/CLV sample < 30")
    if not bpen.get("teamRows"):
        blockers.append("Bpen WHIP35 team rows missing")
    if hist_ml.get("rowsUsed", 0) < 1000:
        blockers.append("Historical Moneyline calibration rows low/missing")

    if blockers:
        actions.append("Keep live 135/136 unchanged.")
        actions.append("Continue collecting odds snapshots and final results.")
        actions.append("Use sidecars for paper A/B only.")
    else:
        actions.append("Enough data for first threshold review.")
        actions.append("Generate threshold candidate changes but require manual approval.")

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "decision": "HOLD_LIVE_THRESHOLDS" if blockers else "READY_FOR_THRESHOLD_REVIEW",
        "blockers": blockers,
        "actions": actions,
        "readiness": readiness.get("ready", {}),
        "historicalMoneylineOverall": hist_ml.get("overall", {}),
        "liveData": live_data,
        "marketRoi": roi.get("all", {}),
        "bpenRows": bpen.get("teamRows", 0),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 192 CALIBRATION CONTROL BOARD",
        "=" * 64,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision: {out['decision']}",
        "",
        "Blockers:",
    ]
    lines += [f"- {b}" for b in blockers] if blockers else ["- none"]
    lines += ["", "Actions:"]
    lines += [f"- {a}" for a in actions]
    lines += [
        "",
        "Live data:",
    ]
    for k, v in live_data.items():
        lines.append(f"- {k}: rows={v.get('rows')} resolved={v.get('resolved')}")
    lines += [
        "",
        f"Historical ML overall: {out['historicalMoneylineOverall']}",
        f"Market ROI: {out['marketRoi']}",
        f"Bpen team rows: {out['bpenRows']}",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
