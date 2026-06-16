from pathlib import Path
from datetime import datetime
import csv
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BASE_CSV = ASTRO / "retrosheet" / "ou_baseballpred_features.csv"
OUT_CSV = ASTRO / "retrosheet" / "ou_full_baseballpred_features.csv"
OUT_JSON = ASTRO / "ASTRODDS-ou-full-baseballpred-features-latest.json"
REPORT = REPORTS / "148_build_ou_full_baseballpred_features_report.txt"

def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def read_rows():
    if not BASE_CSV.exists():
        return []
    with BASE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows = read_rows()
    enhanced = []

    for r in rows:
        away_rf = fnum(r.get("away_rf_162"))
        away_ra = fnum(r.get("away_ra_162"))
        home_rf = fnum(r.get("home_rf_162"))
        home_ra = fnum(r.get("home_ra_162"))
        league = fnum(r.get("league_avg_total_rolling"), 9.0)
        proj_simple = fnum(r.get("projected_simple_total"), league)
        total = fnum(r.get("total_runs"))

        # Safe BaseballPred-style proxies from Retrosheet only.
        # These are not true OBP/SLG/WHIP; they are placeholders until real files exist.
        away_offense_index = away_rf - (league / 2.0)
        home_offense_index = home_rf - (league / 2.0)
        away_defense_risk = away_ra - (league / 2.0)
        home_defense_risk = home_ra - (league / 2.0)

        offense_combo = away_rf + home_rf
        defense_combo = away_ra + home_ra
        volatility_proxy = abs(away_rf - away_ra) + abs(home_rf - home_ra)
        run_environment_index = proj_simple - league

        # Proxies shaped like BaseballPred columns.
        obp_162_proxy = clamp(0.315 + (offense_combo - league) * 0.010, 0.270, 0.380)
        slg_162_proxy = clamp(0.400 + (offense_combo - league) * 0.025, 0.320, 0.540)
        starter_whip_35_proxy = clamp(1.30 + (defense_combo - league) * 0.055, 0.95, 1.80)
        starter_so_perc_10_proxy = clamp(0.215 - (defense_combo - league) * 0.010, 0.120, 0.330)
        bullpen_whip_75_proxy = clamp(1.28 + (defense_combo - league) * 0.050, 0.95, 1.85)
        bullpen_so_perc_75_proxy = clamp(0.220 - (defense_combo - league) * 0.008, 0.120, 0.340)
        bullpen_whip_35_proxy = clamp(1.30 + (defense_combo - league) * 0.060, 0.95, 1.90)

        x = dict(r)
        x.update({
            "away_offense_index": round(away_offense_index, 4),
            "home_offense_index": round(home_offense_index, 4),
            "away_defense_risk": round(away_defense_risk, 4),
            "home_defense_risk": round(home_defense_risk, 4),
            "offense_combo": round(offense_combo, 4),
            "defense_combo": round(defense_combo, 4),
            "volatility_proxy": round(volatility_proxy, 4),
            "run_environment_index": round(run_environment_index, 4),

            "OBP_162_proxy": round(obp_162_proxy, 4),
            "SLG_162_proxy": round(slg_162_proxy, 4),
            "Strt_WHIP_35_proxy": round(starter_whip_35_proxy, 4),
            "Strt_SO_perc_10_proxy": round(starter_so_perc_10_proxy, 4),
            "Bpen_WHIP_75_proxy": round(bullpen_whip_75_proxy, 4),
            "Bpen_SO_perc_75_proxy": round(bullpen_so_perc_75_proxy, 4),
            "Bpen_WHIP_35_proxy": round(bullpen_whip_35_proxy, 4),

            "target_total_runs": total,
        })
        enhanced.append(x)

    fields = []
    for r in enhanced:
        for k in r.keys():
            if k not in fields:
                fields.append(k)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in enhanced:
            w.writerow(r)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_feature_build_only",
        "warning": "Advanced BaseballPred columns are proxy features derived from Retrosheet runs, not true OBP/SLG/WHIP.",
        "baseCsv": str(BASE_CSV),
        "outputCsv": str(OUT_CSV),
        "rows": len(enhanced),
        "proxyFeatures": [
            "OBP_162_proxy","SLG_162_proxy","Strt_WHIP_35_proxy","Strt_SO_perc_10_proxy",
            "Bpen_WHIP_75_proxy","Bpen_SO_perc_75_proxy","Bpen_WHIP_35_proxy"
        ],
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 148 BUILD FULL O/U BASEBALLPRED FEATURES",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Adds BaseballPred-style proxy columns from Retrosheet only.",
        "- WARNING: proxies are not true OBP/SLG/WHIP until real source files are added.",
        "",
        f"Base CSV: {BASE_CSV}",
        f"Output CSV: {OUT_CSV}",
        f"Rows: {len(enhanced)}",
        "",
        "Proxy features added:",
    ]
    for p in out["proxyFeatures"]:
        lines.append(f"- {p}")

    if enhanced:
        lines += ["", "Preview:"]
        for r in enhanced[:5]:
            lines.append(
                f"- {r['date']} {r['away_team']} @ {r['home_team']} | "
                f"target={r['target_total_runs']} proj={r['projected_simple_total']} "
                f"OBPproxy={r['OBP_162_proxy']} WHIPproxy={r['Strt_WHIP_35_proxy']}"
            )

    lines += ["", f"JSON: {OUT_JSON}"]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
