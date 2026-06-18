from pathlib import Path
from datetime import datetime, timezone
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"

REPORT = REPORTS / "209_moneyline_model_probability_source_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-model-probability-source-audit-latest.json"

CANDIDATE_FILES = [
    ASTRO / "ASTRODDS-public-board-categories-latest.json",
    ASTRO / "ASTRODDS-engine-final-signals-latest.json",
    ASTRO / "ASTRODDS-full-slate-context-final-latest.csv",
    ASTRO / "ASTRODDS-full-slate-context-input-latest.csv",
    ASTRO / "ASTRODDS-moneyline-baseballpred-sidecar-latest.json",
    ASTRO / "ASTRODDS-baseballpred-full-slate-ranker-latest.json",
    ASTRO / "ASTRODDS-full-slate-game-board-clean-latest.json",
    ASTRO / "ASTRODDS-moneyline-baseballpred-full-slate-fixed-latest.json",
    PROCESSED / "mlb_moneyline_features.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers.csv",
    PROCESSED / "mlb_moneyline_features_with_bullpen.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
]

PROB_HINTS = ["prob", "model", "calibrated", "win", "edge", "score", "grade", "decision", "price"]
GAME_HINTS = ["game", "matchup", "away", "home", "team", "pick"]

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def read_csv(path, limit=5):
    if not path.exists():
        return [], []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append(row)
            return reader.fieldnames or [], rows
    except Exception:
        return [], []

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def flatten(obj, out=None):
    if out is None:
        out = []
    if isinstance(obj, list):
        for x in obj:
            flatten(x, out)
    elif isinstance(obj, dict):
        out.append(obj)
        for v in obj.values():
            flatten(v, out)
    return out

def fnum(v):
    try:
        s = str(v).strip().replace("%", "").replace("+", "")
        if not s:
            return None
        return float(s)
    except Exception:
        return None

def analyze_rows(rows):
    if not rows:
        return {"columns": [], "probLikeColumns": [], "gameLikeColumns": [], "sampleRows": []}

    cols = sorted(set(k for r in rows for k in r.keys()))
    prob_cols = []
    game_cols = []

    for c in cols:
        cn = norm(c)
        if any(h in cn for h in PROB_HINTS):
            prob_cols.append(c)
        if any(h in cn for h in GAME_HINTS):
            game_cols.append(c)

    sample = []
    for r in rows[:5]:
        compact = {}
        for c in prob_cols + game_cols:
            if c in r and str(r.get(c, "")).strip() != "":
                compact[c] = r.get(c)
        sample.append(compact)

    numeric_stats = {}
    for c in prob_cols:
        vals = [fnum(r.get(c)) for r in rows[:200] if fnum(r.get(c)) is not None]
        if vals:
            numeric_stats[c] = {
                "count": len(vals),
                "min": min(vals),
                "max": max(vals),
                "avg": sum(vals) / len(vals),
                "looks_prob_0_1": all(0 <= v <= 1 for v in vals),
                "looks_percent": any(1 < v <= 100 for v in vals),
                "has_extreme_99": any(v >= 0.98 for v in vals if v <= 1) or any(v >= 98 for v in vals),
            }

    return {
        "columns": cols,
        "probLikeColumns": prob_cols,
        "gameLikeColumns": game_cols,
        "numericStats": numeric_stats,
        "sampleRows": sample,
    }

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    results = []

    for path in CANDIDATE_FILES:
        item = {"file": str(path), "exists": path.exists()}
        if not path.exists():
            results.append(item)
            continue

        if path.suffix.lower() == ".csv":
            cols, rows = read_csv(path, limit=200)
            item.update(analyze_rows(rows))
            item["rowSampleCount"] = len(rows)
        else:
            data = load_json(path)
            rows = flatten(data)
            # only dict rows with meaningful keys
            rows = [r for r in rows if isinstance(r, dict)]
            item.update(analyze_rows(rows))
            item["rowSampleCount"] = len(rows)

        results.append(item)

    usable = []
    suspicious = []

    for r in results:
        if not r.get("exists"):
            continue
        prob_cols = r.get("probLikeColumns", [])
        game_cols = r.get("gameLikeColumns", [])
        if prob_cols and game_cols:
            usable.append(r)
        stats = r.get("numericStats", {})
        for col, st in stats.items():
            if st.get("has_extreme_99"):
                suspicious.append({"file": r["file"], "column": col, "stats": st})

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "filesAudited": len(results),
        "usableSourceCount": len(usable),
        "suspiciousExtremeProbabilityColumns": suspicious,
        "results": results,
        "recommendation": "Use only columns with real calibrated model probabilities or explicit public board modelProbability. Reject synthetic target_home_win/home_win_pct_before for today's picks unless calibrated.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 209 MONEYLINE MODEL PROBABILITY SOURCE AUDIT",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Files audited: {out['filesAudited']}",
        f"Usable source candidates: {out['usableSourceCount']}",
        "",
        "Usable source candidates:",
    ]

    for r in usable:
        lines.append(f"- {Path(r['file']).name}")
        lines.append(f"  prob-like columns: {r.get('probLikeColumns')[:20]}")
        lines.append(f"  game/team columns: {r.get('gameLikeColumns')[:20]}")
        if r.get("sampleRows"):
            lines.append(f"  sample: {r.get('sampleRows')[0]}")

    lines += ["", "Suspicious extreme probability columns:"]
    if not suspicious:
        lines.append("- none")
    else:
        for s in suspicious[:30]:
            lines.append(f"- {Path(s['file']).name} | {s['column']} | {s['stats']}")

    lines += [
        "",
        "Decision:",
        "- Do not score all Moneyline teams until we identify a true calibrated probability source per game/team.",
        "- Current Moneyline-first board is OK for display, but NO_BET rows without model/edge should stay NO_BET.",
        "- Official picks remain from public board / live 135 only.",
        "",
        f"JSON: {OUT_JSON}",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
