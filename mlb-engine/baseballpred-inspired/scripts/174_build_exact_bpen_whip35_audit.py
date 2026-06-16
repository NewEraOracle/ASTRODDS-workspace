from pathlib import Path
from datetime import datetime
import csv, json, re
from collections import defaultdict, deque

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

REPORT = REPORTS / "174_build_exact_bpen_whip35_audit_report.txt"
OUT_JSON = ASTRO / "ASTRODDS-exact-bpen-whip35-latest.json"
OUT_CSV = ASTRO / "ASTRODDS-exact-bpen-whip35-latest.csv"

CANDIDATES = [
    PROCESSED / "mlb_bullpen_features.csv",
    PROCESSED / "mlb_moneyline_features_with_bullpen.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
    PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
    ASTRO / "VVS-bullpen-context-latest.csv",
]

def read_csv(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def fnum(v, default=None):
    try:
        s = str(v).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def find_col(cols, terms):
    low = {c: c.lower() for c in cols}
    for c, lc in low.items():
        if any(t in lc for t in terms):
            return c
    return None

def norm_team(v):
    return re.sub(r"\s+", " ", str(v or "").strip().lower())

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    audit = []
    output_rows = []
    exact_sources = []

    for path in CANDIDATES:
        rows = read_csv(path)
        if not rows:
            continue
        cols = list(rows[0].keys())

        date_col = find_col(cols, ["game_date", "date"])
        team_col = find_col(cols, ["team"])
        ip_col = find_col(cols, ["bullpen_ip", "bpen_ip", "reliever_ip", "ip"])
        hits_col = find_col(cols, ["bullpen_hits", "bpen_hits", "reliever_hits", "hits_allowed", "hits"])
        walks_col = find_col(cols, ["bullpen_walks", "bpen_walks", "reliever_walks", "walks_allowed", "walks", "bb"])

        has_exact = bool(date_col and team_col and ip_col and hits_col and walks_col)
        audit.append({
            "path": str(path),
            "rows": len(rows),
            "date_col": date_col,
            "team_col": team_col,
            "ip_col": ip_col,
            "hits_col": hits_col,
            "walks_col": walks_col,
            "can_build_exact_whip35": has_exact,
            "columns_preview": cols[:60],
        })

        if not has_exact:
            continue

        exact_sources.append(str(path))
        rows_sorted = sorted(rows, key=lambda r: str(r.get(date_col, "")))
        history = defaultdict(lambda: deque(maxlen=35))

        for r in rows_sorted:
            team = norm_team(r.get(team_col))
            if not team:
                continue
            prev = list(history[team])
            ip_sum = sum(x["ip"] for x in prev)
            hw_sum = sum(x["hits"] + x["walks"] for x in prev)
            whip35 = (hw_sum / ip_sum) if ip_sum > 0 else None

            ip = fnum(r.get(ip_col), 0.0)
            hits = fnum(r.get(hits_col), 0.0)
            walks = fnum(r.get(walks_col), 0.0)

            output_rows.append({
                "date": r.get(date_col, ""),
                "team": team,
                "bpen_whip_35_exact": "" if whip35 is None else round(whip35, 4),
                "source": str(path),
                "sample_games": len(prev),
            })

            if ip and ip > 0:
                history[team].append({"ip": ip, "hits": hits or 0.0, "walks": walks or 0.0})

    if output_rows:
        with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
            fields = ["date", "team", "bpen_whip_35_exact", "source", "sample_games"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in output_rows:
                w.writerow(r)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "exact_bpen_whip35_builder_or_audit",
        "exactSources": exact_sources,
        "rowsBuilt": len(output_rows),
        "csv": str(OUT_CSV) if output_rows else None,
        "audit": audit,
        "decision": "EXACT_BPen_WHIP35_READY" if output_rows else "MISSING bullpen hits/walks/IP by team/date source",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 174 EXACT BPEN WHIP35 BUILDER / AUDIT",
        "=" * 72,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Decision: {out['decision']}",
        f"Rows built: {len(output_rows)}",
        "",
        "Sources audited:",
    ]
    for a in audit:
        lines.append(f"- {a['path']} | rows={a['rows']} | exact={a['can_build_exact_whip35']}")
        lines.append(f"  date={a['date_col']} team={a['team_col']} ip={a['ip_col']} hits={a['hits_col']} walks={a['walks_col']}")
    if output_rows:
        lines += ["", f"CSV: {OUT_CSV}"]
    lines += ["", "Rule:", "- If no exact source exists, do not fake Bpen_WHIP_35.", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
