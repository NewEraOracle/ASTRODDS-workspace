from pathlib import Path
import json
import urllib.request
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]

API_URL = "http://127.0.0.1:3000/api/astrodds/best-bets/today"
REPORT = BASE / "reports" / "06_feature_readiness_audit_report.txt"

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

def is_vvs(row):
    market = to_float(row.get("marketProbability"))
    model = to_float(row.get("calibratedProbability"))
    edge = edge_pct(row)
    gap = model_gap_pct(row)

    selected = row.get("selectedSide")
    away = row.get("awayTeam")
    home = row.get("homeTeam")

    return (
        row.get("status") in ["daily_pick", "buy"]
        and row.get("marketType") == "moneyline"
        and selected and (selected == away or selected == home)
        and market is not None and 0.30 <= market <= 0.75
        and model is not None
        and edge is not None and 3 <= edge <= 25
        and gap is not None and gap >= 8
        and row.get("matchConfidence") in ["high", "medium"]
        and row.get("riskLevel") not in ["high", "unknown"]
    )

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

def fetch_best_bets():
    with urllib.request.urlopen(API_URL, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))

def main():
    data = fetch_best_bets()
    rows = data.get("bestBetRows", [])
    vvs = [r for r in rows if is_vvs(r)]

    counters = defaultdict(int)
    lines = []

    lines.append("ASTRODDS 06 FEATURE READINESS AUDIT")
    lines.append("=" * 42)
    lines.append(f"API rows: {len(rows)}")
    lines.append(f"VVS rows: {len(vvs)}")
    lines.append("")
    lines.append("Goal:")
    lines.append("Audit what data/features are still missing before making ASTRODDS smarter.")
    lines.append("")

    for row in vvs:
        blob = text_blob(row)

        missing = []

        if "sportsbook odds fallback connected with a positive edge" in blob:
            missing.append("generic_reason_only")
            counters["generic_reason_only"] += 1

        if "pitcher" not in blob:
            missing.append("pitcher_context_missing")
            counters["pitcher_context_missing"] += 1

        if "bullpen" not in blob:
            missing.append("bullpen_context_missing")
            counters["bullpen_context_missing"] += 1

        if "lineup" not in blob:
            missing.append("lineup_context_missing")
            counters["lineup_context_missing"] += 1

        if "weather" not in blob:
            missing.append("weather_context_missing")
            counters["weather_context_missing"] += 1

        if "injury" not in blob and "injuries" not in blob:
            missing.append("injury_context_missing")
            counters["injury_context_missing"] += 1

        if "alias" in blob:
            missing.append("alias_warning_present")
            counters["alias_warning_present"] += 1

        edge = round(edge_pct(row), 2)
        gap = round(model_gap_pct(row), 2)

        lines.append(
            f"- {row.get('awayTeam')} @ {row.get('homeTeam')} | "
            f"Pick: {row.get('selectedSide')} | "
            f"Edge: {edge}% | Gap: {gap}% | "
            f"Missing: {', '.join(missing) if missing else 'none'}"
        )

    lines.append("")
    lines.append("Feature readiness summary:")
    for key in sorted(counters.keys()):
        lines.append(f"- {key}: {counters[key]}")

    lines.append("")
    lines.append("Next recommended build order:")
    lines.append("1. Improve reasons: show TeamStrength / RecentForm / Pythagorean / Edge / Gap.")
    lines.append("2. Add backend fields: modelProbabilityGapPct, vvsEligible, vvsReason, vvsRank.")
    lines.append("3. Add pitcher context from probable pitchers.")
    lines.append("4. Add bullpen fatigue.")
    lines.append("5. Add lineup / injuries.")
    lines.append("6. Add weather / park factor.")
    lines.append("")
    lines.append("Rule:")
    lines.append("Do not add new betting logic until current VVS picks are resolved.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()
