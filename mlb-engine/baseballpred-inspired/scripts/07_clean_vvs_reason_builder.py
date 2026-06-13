from pathlib import Path
import csv
import json
import urllib.request
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"

ASTRODDS_DIR = ROOT / ".astrodds"
REPORTS = BASE / "reports"

FINAL_CSV = ASTRODDS_DIR / "VVS-clean-final-latest.csv"
FINAL_JSON = ASTRODDS_DIR / "VVS-clean-final-latest.json"
REPORT = REPORTS / "07_clean_vvs_reason_builder_report.txt"

ASTRODDS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def edge_pct(row):
    diagnostic = to_float(row.get("diagnosticCalibratedEdgePct"))
    if diagnostic is not None:
        return diagnostic

    model = to_float(row.get("calibratedProbability"))
    market = to_float(row.get("marketProbability"))

    if model is None or market is None:
        return None

    return (model - market) * 100

def model_gap_pct(row):
    model = to_float(row.get("calibratedProbability"))
    if model is None or model <= 0 or model >= 1:
        return None
    return abs((model * 2) - 1) * 100

def text_blob(row):
    parts = []
    for key in [
        "mainReason",
        "whyDailyPick",
        "whyNotStrongBuy",
        "warnings",
        "reasons",
        "downgradeReasons",
        "blockReasons",
        "gameStatusBlockReasons",
    ]:
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value:
            parts.append(str(value))
    return " | ".join(parts).lower()

def has_alias_warning(row):
    blob = text_blob(row)
    return "alias" in blob or "other mlb team" in blob

def is_vvs(row):
    market = to_float(row.get("marketProbability"))
    model = to_float(row.get("calibratedProbability"))
    edge = edge_pct(row)
    gap = model_gap_pct(row)

    selected = row.get("selectedSide")
    away = row.get("awayTeam")
    home = row.get("homeTeam")

    selected_is_team = selected and (selected == away or selected == home)

    return (
        row.get("status") in ["daily_pick", "buy"]
        and row.get("marketType") == "moneyline"
        and selected_is_team
        and market is not None and 0.30 <= market <= 0.75
        and model is not None
        and edge is not None and 3 <= edge <= 25
        and gap is not None and gap >= 8
        and row.get("matchConfidence") in ["high", "medium"]
        and row.get("riskLevel") not in ["high", "unknown"]
    )

def edge_bucket(edge):
    if edge < 5:
        return "3-5%"
    if edge < 10:
        return "5-10%"
    if edge < 15:
        return "10-15%"
    return "15-25%"

def rank_score(row):
    edge = edge_pct(row) or 0
    gap = model_gap_pct(row) or 0
    status_bonus = 100 if row.get("status") == "daily_pick" else 50
    confidence_bonus = 25 if row.get("matchConfidence") == "high" else 10
    return status_bonus + confidence_bonus + (edge * 3) + gap

def build_clean_reason(row):
    market = to_float(row.get("marketProbability"))
    model = to_float(row.get("calibratedProbability"))
    edge = edge_pct(row)
    gap = model_gap_pct(row)

    return (
        f"VVS clean moneyline: model {model * 100:.1f}% vs market {market * 100:.1f}%, "
        f"edge +{edge:.2f}%, model gap {gap:.1f}%, "
        f"confidence {row.get('matchConfidence')}, risk {row.get('riskLevel')}. "
        f"Model V1 uses 60% previous season record, 20% recent form, 20% Pythagorean strength."
    )

def fetch_best_bets():
    with urllib.request.urlopen(API_URL, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))

def main():
    snapshot_time = datetime.utcnow().isoformat() + "Z"

    data = fetch_best_bets()
    rows = data.get("bestBetRows", [])

    raw_vvs = [r for r in rows if is_vvs(r)]
    alias_rejected = [r for r in raw_vvs if has_alias_warning(r)]
    clean_candidates = [r for r in raw_vvs if not has_alias_warning(r)]

    grouped = {}

    for row in clean_candidates:
        game_key = f"{row.get('awayTeam')} @ {row.get('homeTeam')}"
        current = grouped.get(game_key)

        if current is None or rank_score(row) > rank_score(current):
            grouped[game_key] = row

    final = list(grouped.values())
    final.sort(key=rank_score, reverse=True)
    final = final[:10]

    output_rows = []

    for row in final:
        market = to_float(row.get("marketProbability"))
        model = to_float(row.get("calibratedProbability"))
        edge = round(edge_pct(row), 2)
        gap = round(model_gap_pct(row), 2)

        output_rows.append({
            "snapshotTime": snapshot_time,
            "gameId": row.get("gameId"),
            "date": row.get("date"),
            "game": f"{row.get('awayTeam')} @ {row.get('homeTeam')}",
            "awayTeam": row.get("awayTeam"),
            "homeTeam": row.get("homeTeam"),
            "pick": row.get("selectedSide"),
            "status": row.get("status"),
            "marketProbability": market,
            "modelProbability": model,
            "edgePct": edge,
            "modelGapPct": gap,
            "edgeBucket": edge_bucket(edge),
            "confidence": row.get("matchConfidence"),
            "risk": row.get("riskLevel"),
            "vvsEligible": True,
            "vvsReason": build_clean_reason(row),
            "result": "pending",
            "paperOnly": True,
        })

    FINAL_JSON.write_text(json.dumps(output_rows, indent=2), encoding="utf-8")

    with FINAL_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "snapshotTime",
            "gameId",
            "date",
            "game",
            "awayTeam",
            "homeTeam",
            "pick",
            "status",
            "marketProbability",
            "modelProbability",
            "edgePct",
            "modelGapPct",
            "edgeBucket",
            "confidence",
            "risk",
            "vvsEligible",
            "vvsReason",
            "result",
            "paperOnly",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    lines = []
    lines.append("ASTRODDS 07 CLEAN VVS REASON BUILDER REPORT")
    lines.append("=" * 48)
    lines.append(f"Snapshot time: {snapshot_time}")
    lines.append(f"API rows: {len(rows)}")
    lines.append(f"Raw VVS candidates: {len(raw_vvs)}")
    lines.append(f"Rejected alias warnings: {len(alias_rejected)}")
    lines.append(f"Clean candidates after alias filter: {len(clean_candidates)}")
    lines.append(f"Final one-pick-per-game VVS rows: {len(output_rows)}")
    lines.append("")
    lines.append("Final clean VVS picks:")

    for row in output_rows:
        lines.append(
            f"- {row['date']} | {row['game']} | Pick: {row['pick']} | "
            f"Edge: {row['edgePct']}% | Gap: {row['modelGapPct']}% | "
            f"Bucket: {row['edgeBucket']}"
        )

    lines.append("")
    lines.append("What this fixed:")
    lines.append("- Removed alias-warning candidates.")
    lines.append("- Removed duplicate/conflicting picks from the same game.")
    lines.append("- Replaced generic reasons with VVS model reasons.")
    lines.append("")
    lines.append(f"CSV: {FINAL_CSV}")
    lines.append(f"JSON: {FINAL_JSON}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
