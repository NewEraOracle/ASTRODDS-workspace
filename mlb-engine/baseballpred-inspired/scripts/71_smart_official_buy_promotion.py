from pathlib import Path
import json
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

ENGINE = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-latest.json"
GATE = ROOT / ".astrodds" / "ASTRODDS-soft-hard-context-gate-latest.json"
BACKUP = ROOT / ".astrodds" / "ASTRODDS-engine-final-signals-before-smart-promotion-latest.json"
REPORT = BASE / "reports" / "71_smart_official_buy_promotion_report.txt"

def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return fallback

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def key(row):
    return f"{row.get('gameId') or ''}|{row.get('game') or ''}|{row.get('pick') or ''}"

def main():
    mode = "apply" if len(sys.argv) > 1 and sys.argv[1].lower() == "apply" else "dry_run"
    generated = datetime.now(timezone.utc).isoformat()

    engine = read_json(ENGINE, [])
    gate = read_json(GATE, [])

    if not isinstance(engine, list):
        engine = []
    if not isinstance(gate, list):
        gate = []

    gate_map = {key(r): r for r in gate if isinstance(r, dict)}

    promoted = []
    output = []

    for row in engine:
        if not isinstance(row, dict):
            continue
        new = dict(row)
        g = gate_map.get(key(row))
        if g and g.get("promotionEligible"):
            original_decision = new.get("finalEngineDecision")
            original_grade = new.get("finalGrade")

            new["originalFinalEngineDecisionBeforeSmartPromotion"] = original_decision
            new["originalFinalGradeBeforeSmartPromotion"] = original_grade
            new["finalEngineDecision"] = "ENGINE_BUY"
            new["finalGrade"] = original_grade if original_grade in ["A+", "A"] else "A"
            new["smartPromotionApplied"] = True
            new["smartPromotionAt"] = generated
            new["smartPromotionStatus"] = g.get("promotionStatus")
            new["smartPromotionReasons"] = g.get("promotionReasons")
            new["publicRiskLabel"] = "MEDIUM" if int(g.get("softWarningCount") or 0) > 0 else "LOW"
            promoted.append(new)
        else:
            new["smartPromotionApplied"] = False
        output.append(new)

    if mode == "apply":
        if ENGINE.exists():
            shutil.copy2(ENGINE, BACKUP)
        write_json(ENGINE, output)

    lines = []
    lines.append("ASTRODDS 71 SMART OFFICIAL BUY PROMOTION REPORT")
    lines.append("=" * 58)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Mode: {mode}")
    lines.append(f"Input engine rows: {len(engine)}")
    lines.append(f"Gate rows: {len(gate)}")
    lines.append(f"Promoted rows: {len(promoted)}")
    lines.append("")
    if mode == "apply":
        lines.append(f"Backup: {BACKUP}")
        lines.append(f"Updated engine final: {ENGINE}")
    else:
        lines.append("Dry run only. No engine file was modified.")
    lines.append("")
    lines.append("Promoted rows:")
    if promoted:
        for r in promoted:
            lines.append(
                f"- {r.get('game')} | Pick: {r.get('pick')} | "
                f"{r.get('originalFinalEngineDecisionBeforeSmartPromotion')} -> {r.get('finalEngineDecision')} | "
                f"Grade={r.get('finalGrade')} | Risk={r.get('publicRiskLabel')} | Reasons={r.get('smartPromotionReasons')}"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Rule: promotion only. No odds scan. No Telegram send. No betting automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()