from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
TARGETS = [SCRIPTS / "132_resolve_clean_moneyline_results_from_mlb.py", SCRIPTS / "145_resolve_clean_ou_results_from_mlb.py"]
REPORT = REPORTS / "163_patch_postponed_suspended_resolvers_report.txt"

SAFETY_FUNCTION = """
def astrodds_safe_game_status(game_obj):
    status = game_obj.get("status", {}) if isinstance(game_obj, dict) else {}
    abstract_state = str(status.get("abstractGameState", "")).lower()
    detailed_state = str(status.get("detailedState", "")).lower()
    coded = str(status.get("codedGameState", "")).upper()
    danger_terms = ["postponed", "suspended", "delayed", "cancelled", "canceled", "rescheduled"]
    if any(t in detailed_state for t in danger_terms):
        return "KEEP_PENDING", detailed_state or coded
    is_final = abstract_state == "final" or "final" in detailed_state or coded in ("F", "FT", "FR")
    if is_final:
        return "FINAL", detailed_state or coded
    return "KEEP_PENDING", detailed_state or coded

"""

def patch_file(path):
    if not path.exists():
        return f"MISSING | {path.name}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "astrodds_safe_game_status" in text:
        return f"SKIP | already patched | {path.name}"
    backup = path.with_suffix(path.suffix + f".before-163-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copyfile(path, backup)
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("class "):
            insert_at = i
            break
    lines.insert(insert_at, SAFETY_FUNCTION)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"PATCHED | {path.name} | backup={backup}"

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = [patch_file(p) for p in TARGETS]
    lines = ["ASTRODDS 163 PATCH POSTPONED/SUSPENDED RESOLVERS", "=" * 70, f"Generated UTC: {datetime.utcnow().isoformat()}Z", "", "Results:"] + [f"- {r}" for r in results]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
if __name__ == "__main__":
    main()
