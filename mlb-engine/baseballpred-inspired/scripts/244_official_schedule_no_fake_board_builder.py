from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FILTER_JSON = ASTRO / "ASTRODDS-moneyline-authoritative-schedule-filter-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-official-schedule-no-fake-board-latest.json"
REPORT = REPORTS / "244_official_schedule_no_fake_board_builder_report.txt"

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def main():
    data = load(FILTER_JSON)
    kept = data.get("keptMoneylineBoard", []) or []
    missing_games = data.get("missingOfficialGames", []) or []

    rows = []
    for r in kept:
        r = dict(r)
        r["boardStatus"] = "PRICE_AVAILABLE"
        rows.append(r)

    # Add placeholders for official games missing price, so dashboard shows the truth instead of silently omitting them.
    for g in missing_games:
        official = g.get("officialGame", "")
        away, home = ("", "")
        if " @ " in official:
            away, home = official.split(" @ ", 1)
        for team in [away, home]:
            rows.append({
                "pick": team,
                "game": official,
                "awayTeam": away,
                "homeTeam": home,
                "price": None,
                "modelProbability": None,
                "currentEdgePct": None,
                "liveMlbStatus": g.get("liveMlbStatus", ""),
                "liveGameDate": g.get("gameDate", ""),
                "liveGamePk": g.get("gamePk", ""),
                "boardStatus": "MISSING_PRICE",
                "status": "MISSING_PRICE",
                "actionStatus": "HOLD_NO_PRICE",
                "mainReason": "Official MLB game exists, but no Moneyline price row is available from the current price board.",
                "riskReason": "Do not evaluate or signal until odds/price source provides this game.",
            })

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "priceRows": len(kept),
        "missingOfficialGames": len(missing_games),
        "rows": len(rows),
        "moneylineBoard": rows,
        "rule": "Dashboard board includes official missing-price placeholders to prevent fake/stale slate confusion.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 244 OFFICIAL SCHEDULE NO-FAKE BOARD BUILDER",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows with prices: {out['priceRows']}",
        f"Official games missing prices: {out['missingOfficialGames']}",
        f"Output rows including placeholders: {out['rows']}",
        "",
        "Missing-price placeholders:",
    ]
    for r in rows:
        if r.get("boardStatus") == "MISSING_PRICE":
            lines.append(f"- {r.get('pick')} | {r.get('game')} | status={r.get('liveMlbStatus')} | action={r.get('actionStatus')}")
    lines += ["", f"JSON: {OUT_JSON}", "Rule: show missing official games as HOLD_NO_PRICE, never replace with stale games."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
