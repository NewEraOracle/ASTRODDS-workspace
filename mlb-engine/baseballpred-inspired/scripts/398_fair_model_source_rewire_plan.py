from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
AUDIT_JSON = ASTRO / "ASTRODDS-396-real-baseball-source-stack-audit-latest.json"
REPORT = REPORTS / "398_fair_model_source_rewire_plan_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-398-fair-model-source-rewire-plan-latest.json"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    audit = load(AUDIT_JSON)
    decision = audit.get("decision", "UNKNOWN")
    board = audit.get("currentBoard", {})

    steps = []
    if decision == "PYBASEBALL_NOT_READY":
        steps = [
            "Install/fix pybaseball in the Python environment used by PowerShell.",
            "Run 378_check_python_pybaseball_tools.ps1.",
            "Run 382_run_real_baseballpred_data_acquisition.ps1 again.",
        ]
    elif decision == "REAL_BASEBALL_DATA_NOT_CONNECTED":
        steps = [
            "Run real source acquisition scripts 379/380/381/382.",
            "Verify output CSVs are non-empty and contain today teams.",
            "Do not change picks until source files are populated.",
        ]
    elif decision == "MODEL_FEATURES_NOT_FULLY_JOINED":
        steps = [
            "Build a join bridge from FanGraphs/Retrosheet/pybaseball outputs into the model fair probability board.",
            "Validate team aliases for Athletics, Angels, White Sox, Cardinals, Guardians.",
            "Compare Fair values against partner screenshot for Angels/Guardians/Orioles/Cardinals.",
        ]
    elif decision == "MARKET_PM_PRICE_NOT_FULLY_JOINED":
        steps = [
            "Model/fair side is mostly ready; focus on PM market price join.",
            "Use official schedule first, then join market PM by exact team side.",
            "Keep complement price fill only when exactly one side is valid.",
        ]
    else:
        steps = [
            "Source stack appears OK; run parity board and validate PM/Fair differences.",
            "Commit only source scripts that are stable.",
        ]

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "currentBoard": board,
        "nextSteps": steps,
        "targetArchitecture": {
            "schedule": "MLB StatsAPI",
            "fairModel": "FanGraphs + Retrosheet + Statcast/pybaseball features",
            "pmPrice": "Market/Polymarket moneyline prices",
            "guards": "ASTRODDS status, stale-game, duplicate-side and bankroll guards",
        },
        "rule": "Fix source stack in layers, not by forcing picks.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 398 FAIR MODEL SOURCE REWIRE PLAN",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision from 396: {decision}",
        "",
        "Current Board:",
        f"- rows: {board.get('rows')}",
        f"- rowsWithPrice: {board.get('rowsWithPrice')}",
        f"- rowsWithModel: {board.get('rowsWithModel')}",
        f"- rowsWithEdge: {board.get('rowsWithEdge')}",
        "",
        "Target architecture:",
        "- MLB StatsAPI = schedule/status/gamePk",
        "- FanGraphs + Retrosheet + Statcast/pybaseball = Fair/modelProbability",
        "- Market/Polymarket = PM/price",
        "- ASTRODDS = edge/grade/guard/stake",
        "",
        "Next steps:",
    ]
    for i, s in enumerate(steps, 1):
        lines.append(f"{i}. {s}")

    lines += ["", f"JSON: {OUT_JSON}", "Rule: do not replace schedule MLB; replace/improve model/fair source."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
