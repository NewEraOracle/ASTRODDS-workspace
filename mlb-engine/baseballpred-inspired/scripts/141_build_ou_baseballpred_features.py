from pathlib import Path
from datetime import datetime
import csv
import json
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

GAMELOG_DIR = ASTRO / "retrosheet" / "gamelogs"
OUT_CSV = ASTRO / "retrosheet" / "ou_baseballpred_features.csv"
OUT_JSON = ASTRO / "ASTRODDS-ou-baseballpred-features-latest.json"
REPORT = REPORTS / "141_build_ou_baseballpred_features_report.txt"

START_YEAR = 1980
ROLL_N = 162

def safe_int(x, default=None):
    try:
        return int(str(x).strip())
    except Exception:
        return default

def mean_last(items, n=ROLL_N, default=4.5):
    vals = items[-n:]
    if not vals:
        return default
    return sum(vals) / len(vals)

def parse_game_log_file(path):
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for parts in reader:
            if len(parts) < 11:
                continue
            date = str(parts[0]).strip()
            if len(date) < 8:
                continue
            year = safe_int(date[:4])
            if year is None or year < START_YEAR:
                continue

            away = str(parts[3]).strip()
            home = str(parts[6]).strip()
            away_runs = safe_int(parts[9])
            home_runs = safe_int(parts[10])

            if not away or not home or away_runs is None or home_runs is None:
                continue

            rows.append({
                "date": date,
                "year": year,
                "away_team": away,
                "home_team": home,
                "away_runs": away_runs,
                "home_runs": home_runs,
                "total_runs": away_runs + home_runs,
            })
    return rows

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(GAMELOG_DIR.glob("gl*.txt"))
    all_games = []
    for p in files:
        all_games.extend(parse_game_log_file(p))

    all_games.sort(key=lambda r: r["date"])

    team_for = {}
    team_against = {}
    league_totals = []
    features = []

    for g in all_games:
        away = g["away_team"]
        home = g["home_team"]
        total = g["total_runs"]

        away_rf_162 = mean_last(team_for.get(away, []))
        away_ra_162 = mean_last(team_against.get(away, []))
        home_rf_162 = mean_last(team_for.get(home, []))
        home_ra_162 = mean_last(team_against.get(home, []))
        league_avg_162 = mean_last(league_totals, n=ROLL_N * 15, default=8.8)

        # BaseballPred-style simple total projection from rolling attack/allowance.
        projected_simple = (
            away_rf_162 + home_rf_162 + away_ra_162 + home_ra_162 + league_avg_162
        ) / 2.5

        features.append({
            "date": g["date"],
            "year": g["year"],
            "away_team": away,
            "home_team": home,
            "away_runs": g["away_runs"],
            "home_runs": g["home_runs"],
            "total_runs": total,
            "away_rf_162": round(away_rf_162, 4),
            "away_ra_162": round(away_ra_162, 4),
            "home_rf_162": round(home_rf_162, 4),
            "home_ra_162": round(home_ra_162, 4),
            "league_avg_total_rolling": round(league_avg_162, 4),
            "projected_simple_total": round(projected_simple, 4),
            "home_field_flag": 1,
        })

        team_for.setdefault(away, []).append(g["away_runs"])
        team_against.setdefault(away, []).append(g["home_runs"])
        team_for.setdefault(home, []).append(g["home_runs"])
        team_against.setdefault(home, []).append(g["away_runs"])
        league_totals.append(total)

    fields = [
        "date","year","away_team","home_team","away_runs","home_runs","total_runs",
        "away_rf_162","away_ra_162","home_rf_162","home_ra_162",
        "league_avg_total_rolling","projected_simple_total","home_field_flag"
    ]

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in features:
            w.writerow(r)

    summary = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_feature_build_only",
        "retrosheetFolder": str(GAMELOG_DIR),
        "filesFound": len(files),
        "gamesParsed1980Plus": len(all_games),
        "featureRows": len(features),
        "firstDate": features[0]["date"] if features else None,
        "lastDate": features[-1]["date"] if features else None,
        "csv": str(OUT_CSV),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 141 BUILD O/U BASEBALLPRED FEATURES",
        "=" * 64,
        f"Generated UTC: {summary['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Uses Retrosheet 1980+ rolling 162 team runs for/against.",
        "",
        f"Retrosheet folder: {GAMELOG_DIR}",
        f"Game log files found: {len(files)}",
        f"Games parsed 1980+: {len(all_games)}",
        f"Feature rows: {len(features)}",
        f"CSV: {OUT_CSV}",
        f"JSON: {OUT_JSON}",
    ]

    if features:
        lines += [
            "",
            "Preview:",
        ]
        for r in features[:5]:
            lines.append(
                f"- {r['date']} {r['away_team']} @ {r['home_team']} | "
                f"total={r['total_runs']} proj={r['projected_simple_total']} "
                f"awayRF162={r['away_rf_162']} homeRF162={r['home_rf_162']}"
            )

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
