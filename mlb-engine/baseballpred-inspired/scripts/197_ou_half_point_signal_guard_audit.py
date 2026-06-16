from pathlib import Path
import json, math
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
OU_JSON = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
REPORT = REPORTS / "197_ou_half_point_signal_guard_audit_report.txt"

def fnum(v):
    try: return float(str(v).strip().replace("+",""))
    except Exception: return None

def is_half(v):
    x = fnum(v)
    if x is None: return False
    return abs(abs(x - math.floor(x)) - 0.5) < 1e-9

def line_of(d):
    for k in ["line","Line","totalLine","total_line","point","Point","ouLine","marketLine"]:
        if k in d: return d.get(k)
    return None

def scan(obj, found):
    if isinstance(obj, dict):
        txt = " ".join(str(obj.get(k,"")) for k in ["pick","Pick","selection","market","type","decision","grade"]).lower()
        line = line_of(obj)
        if line is not None and ("over" in txt or "under" in txt or "o/u" in txt):
            found.append({
                "game": obj.get("game") or obj.get("Game") or "",
                "pick": obj.get("pick") or obj.get("Pick") or "",
                "line": line,
                "half": is_half(line),
                "grade": obj.get("grade") or obj.get("decision") or "",
            })
        for v in obj.values(): scan(v, found)
    elif isinstance(obj, list):
        for v in obj: scan(v, found)

def main():
    found = []
    if OU_JSON.exists():
        scan(json.loads(OU_JSON.read_text(encoding="utf-8")), found)
    half = [r for r in found if r["half"]]
    blocked = [r for r in found if not r["half"]]
    lines = [
        "ASTRODDS 197 O/U HALF-POINT SIGNAL GUARD AUDIT",
        "=" * 68,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        f"O/U rows found: {len(found)}",
        f"Half-point rows allowed: {len(half)}",
        f"Whole-number rows blocked for Telegram: {len(blocked)}",
        "",
        "Blocked preview:",
    ]
    for r in blocked[:50]:
        lines.append(f"- line={r['line']} | {r['pick']} | {r['game']} | {r['grade']}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
