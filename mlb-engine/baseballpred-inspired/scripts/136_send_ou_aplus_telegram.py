from pathlib import Path
from datetime import datetime
import json, math, runpy, shutil, sys, traceback

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
SCRIPTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "scripts"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BASE_SCRIPT = SCRIPTS / "136_send_ou_aplus_telegram_base.py"
OU_JSON = ASTRO / "ASTRODDS-over-under-expected-total-model-latest.json"
REPORT = REPORTS / "197_ou_half_point_signal_guard_report.txt"

LINE_KEYS = ["line","Line","totalLine","total_line","point","Point","ouLine","marketLine"]
PICK_KEYS = ["pick","Pick","selection","Selection"]

def fnum(v):
    try:
        return float(str(v).strip().replace("+",""))
    except Exception:
        return None

def is_half_point(v):
    x = fnum(v)
    if x is None:
        return False
    return abs(abs(x - math.floor(x)) - 0.5) < 1e-9

def get_line(row):
    for k in LINE_KEYS:
        if k in row:
            return row.get(k)
    return None

def is_ou_row(row):
    text = " ".join(str(row.get(k, "")) for k in PICK_KEYS + ["market","type","decision","grade"]).lower()
    return ("over" in text) or ("under" in text) or ("o/u" in text)

def filter_obj(obj, stats, path="root"):
    if isinstance(obj, list):
        out = []
        for i, item in enumerate(obj):
            if isinstance(item, dict) and is_ou_row(item):
                line = get_line(item)
                if line is not None and not is_half_point(line):
                    stats["removed"] += 1
                    stats["removedRows"].append({
                        "path": f"{path}[{i}]",
                        "game": item.get("game") or item.get("Game") or "",
                        "pick": item.get("pick") or item.get("Pick") or "",
                        "line": line,
                        "grade": item.get("grade") or item.get("decision") or "",
                    })
                    continue
                if line is not None and is_half_point(line):
                    stats["keptHalfPoint"] += 1
            out.append(filter_obj(item, stats, f"{path}[{i}]"))
        return out
    if isinstance(obj, dict):
        return {k: filter_obj(v, stats, f"{path}.{k}") for k, v in obj.items()}
    return obj

def write_report(lines):
    REPORTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def main():
    lines = [
        "ASTRODDS 197 O/U HALF-POINT SIGNAL GUARD",
        "=" * 64,
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
        "Rule:",
        "- Telegram O/U signals can only send .5 lines.",
        "- Whole-number totals like 8 or 9 are blocked before 136 sends.",
        "- Original O/U JSON is restored after send.",
        "",
        f"OU JSON: {OU_JSON}",
        f"Base script: {BASE_SCRIPT}",
    ]

    if not OU_JSON.exists():
        lines += ["", "STOP: O/U JSON missing."]
        write_report(lines)
        sys.exit(1)

    if not BASE_SCRIPT.exists():
        lines += ["", "STOP: base 136 script missing."]
        write_report(lines)
        sys.exit(1)

    original = OU_JSON.read_text(encoding="utf-8")
    backup = OU_JSON.with_suffix(".before-half-point-filter.json")

    try:
        data = json.loads(original)
        stats = {"removed": 0, "keptHalfPoint": 0, "removedRows": []}
        filtered = filter_obj(data, stats)
        shutil.copyfile(OU_JSON, backup)
        OU_JSON.write_text(json.dumps(filtered, indent=2), encoding="utf-8")

        lines += [
            "",
            "Filter result:",
            f"- kept half-point O/U rows: {stats['keptHalfPoint']}",
            f"- removed whole-number O/U rows: {stats['removed']}",
        ]
        if stats["removedRows"]:
            lines += ["", "Removed rows:"]
            for r in stats["removedRows"][:50]:
                lines.append(f"- line={r['line']} | {r['pick']} | {r['game']} | {r['grade']}")
        write_report(lines)

        runpy.run_path(str(BASE_SCRIPT), run_name="__main__")

    except SystemExit:
        raise
    except Exception:
        lines += ["", "ERROR:", traceback.format_exc()]
        write_report(lines)
        sys.exit(1)
    finally:
        try:
            OU_JSON.write_text(original, encoding="utf-8")
        except Exception:
            pass

if __name__ == "__main__":
    main()
