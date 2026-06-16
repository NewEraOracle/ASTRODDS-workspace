from pathlib import Path
from datetime import datetime
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
OUT_JSON = ASTRO / "ASTRODDS-baseballpred-feature-bridge-latest.json"
REPORT = REPORTS / "168_build_baseballpred_feature_bridge_report.txt"

SOURCE_FILES = [
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    PROCESSED / "mlb_moneyline_features_with_lineup.csv",
    PROCESSED / "mlb_lineup_player_features.csv",
    PROCESSED / "mlb_bullpen_features.csv",
    ASTRO / "ASTRODDS-advanced-pitcher-team-metrics-latest.csv",
    ASTRO / "VVS-pitcher-context-latest.csv",
    ASTRO / "VVS-bullpen-context-latest.csv",
]

def norm(s):
    s = str(s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def read_csv(path, max_rows=30000):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            rows = list(csv.DictReader(f))
            return rows[-max_rows:]
    except Exception:
        return []

def find_col(row, terms):
    for k in row.keys():
        lk = k.lower()
        if any(t in lk for t in terms):
            return k
    return None

def game_key(row):
    game = row.get("game") or row.get("Game") or ""
    date = row.get("date") or row.get("game_date") or row.get("snapshotTime") or ""
    home = row.get("home_team") or row.get("homeTeam") or ""
    away = row.get("away_team") or row.get("awayTeam") or ""
    if game:
        return norm(str(date)[:10] + "|" + game)
    return norm(str(date)[:10] + "|" + away + "|" + home)

def extract_features(row):
    mapping = {
        "OBP_162_or_proxy": ["obp_162", "obp_proxy", "obp"],
        "SLG_162_or_proxy": ["slg_162", "slg_proxy", "slg"],
        "starter_WHIP_or_proxy": ["starter_whip", "strt_whip", "pitcher_whip", "whip"],
        "starter_SO_or_proxy": ["starter_so", "strt_so", "pitcher_so", "strikeout", "so_perc"],
        "bullpen_WHIP_or_proxy": ["bullpen_whip", "bpen_whip", "whip"],
        "bullpen_SO_or_proxy": ["bullpen_so", "bpen_so", "reliever_so", "strikeout"],
        "bullpen_fatigue": ["bullpenfatigue", "fatigue"],
        "weather_or_park": ["weather", "wind", "temp", "park", "ballpark"],
        "lineup_strength": ["lineup_strength", "top4", "lineup_status", "missing_key_batters"],
    }
    out = {}
    for name, terms in mapping.items():
        hits = {}
        for k, v in row.items():
            lk = k.lower().replace("_", "")
            if any(t.replace("_","") in lk for t in terms):
                hits[k] = v
        if hits:
            out[name] = hits
    return out

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    bridge = {}
    source_counts = {}

    for path in SOURCE_FILES:
        rows = read_csv(path)
        source_counts[str(path)] = len(rows)
        for r in rows:
            k = game_key(r)
            if not k or k == "|":
                continue
            feats = extract_features(r)
            if not feats:
                continue
            rec = bridge.setdefault(k, {"sources": [], "features": {}})
            rec["sources"].append(str(path))
            for fk, fv in feats.items():
                rec["features"].setdefault(fk, {}).update(fv)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "feature_bridge_only",
        "sourceCounts": source_counts,
        "bridgeRows": len(bridge),
        "bridge": bridge,
        "note": "Feature bridge includes true columns if present and proxy columns when only proxy exists.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 168 BUILD BASEBALLPRED FEATURE BRIDGE",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Source rows:",
    ]
    for p, n in source_counts.items():
        lines.append(f"- {p}: {n}")
    lines += ["", f"Bridge rows: {len(bridge)}", "", "Preview:"]
    for i, (k, v) in enumerate(list(bridge.items())[:10]):
        lines.append(f"- {k} | featureGroups={list(v['features'].keys())}")
    lines += ["", f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
