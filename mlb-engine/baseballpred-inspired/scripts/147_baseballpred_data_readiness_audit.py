from pathlib import Path
from datetime import datetime
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

REPORT = REPORTS / "147_baseballpred_data_readiness_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-baseballpred-data-readiness-latest.json"

SEARCH_ROOTS = [
    ROOT,
    ASTRO,
    ROOT / "mlb-engine",
]

NEEDED_FEATURES = {
    "retrosheet_gamelogs": ["gl*.txt"],
    "batting_obp_slg": ["*bat*.csv", "*hitting*.csv", "*obp*.csv", "*slg*.csv"],
    "starter_pitching": ["*starter*.csv", "*pitcher*.csv", "*whip*.csv"],
    "bullpen": ["*bullpen*.csv", "*bpen*.csv", "*reliever*.csv"],
    "weather_ballpark": ["*weather*.csv", "*ballpark*.csv", "*park*.csv"],
    "lineups": ["*lineup*.csv", "*injury*.csv"],
    "historical_totals_lines": ["*total*.csv", "*over_under*.csv", "*ou*.csv", "*odds*.csv"],
}

def find_matches(patterns, max_items=30):
    found = []
    seen = set()
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for pat in patterns:
            for p in root.rglob(pat):
                if p.is_file() and str(p) not in seen:
                    seen.add(str(p))
                    found.append(str(p))
                    if len(found) >= max_items:
                        return found
    return found

def sniff_csv_columns(path, max_cols=60):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            row = next(reader, [])
            return row[:max_cols]
    except Exception:
        return []

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    readiness = {}
    for key, patterns in NEEDED_FEATURES.items():
        matches = find_matches(patterns)
        readiness[key] = {
            "found": bool(matches),
            "count": len(matches),
            "examples": matches[:10],
            "columnsPreview": sniff_csv_columns(matches[0]) if matches and matches[0].lower().endswith(".csv") else [],
        }

    # Specific Retrosheet check
    retro_dir = ASTRO / "retrosheet" / "gamelogs"
    retro_files = sorted(retro_dir.glob("gl*.txt")) if retro_dir.exists() else []
    readiness["retrosheet_gamelogs"]["found"] = bool(retro_files)
    readiness["retrosheet_gamelogs"]["count"] = len(retro_files)
    readiness["retrosheet_gamelogs"]["examples"] = [str(p) for p in retro_files[:10]]

    complete = {
        "core_retrosheet": readiness["retrosheet_gamelogs"]["found"],
        "advanced_batting": readiness["batting_obp_slg"]["found"],
        "starter_pitching": readiness["starter_pitching"]["found"],
        "bullpen": readiness["bullpen"]["found"],
        "weather_ballpark": readiness["weather_ballpark"]["found"],
        "lineups": readiness["lineups"]["found"],
        "historical_totals_lines": readiness["historical_totals_lines"]["found"],
    }

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_readiness_only",
        "complete": complete,
        "readiness": readiness,
        "decision": "Do not replace live O/U until starter/bullpen/true historical totals are present and backtested.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 147 BASEBALLPRED DATA READINESS AUDIT",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar audit only.",
        "- Does not touch live Telegram.",
        "- Finds which BaseballPred-level data sources are actually available.",
        "",
        "Readiness:",
    ]

    for key, val in complete.items():
        lines.append(f"- {key}: {'YES' if val else 'NO'}")

    lines += ["", "Sources found:"]
    for key, val in readiness.items():
        lines.append(f"- {key}: count={val['count']}")
        for ex in val.get("examples", [])[:3]:
            lines.append(f"  - {ex}")
        cols = val.get("columnsPreview", [])
        if cols:
            lines.append(f"  columns: {cols[:12]}")

    lines += [
        "",
        "Decision:",
        "- Retrosheet can support rolling team scoring features.",
        "- Full BaseballPred needs OBP/SLG, starter pitching, bullpen, weather/park, lineups, and true historical totals lines.",
        "- Live Telegram stays on current safe O/U A+ rule until V2 wins backtests.",
        "",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
