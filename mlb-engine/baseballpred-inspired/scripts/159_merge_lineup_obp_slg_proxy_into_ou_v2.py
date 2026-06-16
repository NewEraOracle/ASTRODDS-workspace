from pathlib import Path
from datetime import datetime
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"

INPUT_JSON = ASTRO / "ASTRODDS-ou-v2-strict-paper-score-latest.json"
LINEUP_CSV = PROCESSED / "mlb_lineup_player_features.csv"
OUT_JSON = ASTRO / "ASTRODDS-ou-v2-batting-context-latest.json"
REPORT = REPORTS / "159_merge_lineup_obp_slg_proxy_into_ou_v2_report.txt"

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    aliases = {
        "blue jays": "toronto blue jays", "red sox": "boston red sox",
        "orioles": "baltimore orioles", "mariners": "seattle mariners",
        "white sox": "chicago white sox", "yankees": "new york yankees",
        "guardians": "cleveland guardians", "brewers": "milwaukee brewers",
        "royals": "kansas city royals", "nationals": "washington nationals",
        "tigers": "detroit tigers", "astros": "houston astros",
        "athletics": "athletics", "oakland athletics": "athletics", "a s": "athletics",
    }
    return aliases.get(s, s)

def parse_game(game):
    g = str(game or "")
    for sep in [" vs. ", " vs ", " @ "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return norm(a), norm(h)
    return "", ""

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        return list(csv.DictReader(f))

def fnum(v, default=None):
    try:
        return float(v)
    except Exception:
        return default

def match_lineup(game, lineup_rows):
    away, home = parse_game(game)
    best = None
    for r in reversed(lineup_rows):
        rh = norm(r.get("home_team", ""))
        ra = norm(r.get("away_team", ""))
        if rh == home and ra == away:
            best = r
            break
        if {rh, ra} == {home, away}:
            best = r
            break
    return best, away, home

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = load_json(INPUT_JSON, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    lineup_rows = read_csv(LINEUP_CSV)

    enriched = []
    matched = 0

    for c in candidates:
        game = c.get("game", "")
        lineup, away_norm, home_norm = match_lineup(game, lineup_rows)
        x = dict(c)
        x["battingContextSource"] = str(LINEUP_CSV)
        x["battingContextMatched"] = bool(lineup)
        x["awayNorm"] = away_norm
        x["homeNorm"] = home_norm

        if lineup:
            matched += 1
            keys = [
                "home_lineup_obp_proxy","away_lineup_obp_proxy",
                "home_lineup_slg_proxy","away_lineup_slg_proxy",
                "home_lineup_strength_score","away_lineup_strength_score",
                "home_top4_batters_available","away_top4_batters_available",
                "home_missing_key_batters_count","away_missing_key_batters_count",
                "home_lineup_status","away_lineup_status"
            ]
            for k in keys:
                x[k] = lineup.get(k, "")

            home_obp = fnum(lineup.get("home_lineup_obp_proxy"), 0.315)
            away_obp = fnum(lineup.get("away_lineup_obp_proxy"), 0.315)
            home_slg = fnum(lineup.get("home_lineup_slg_proxy"), 0.400)
            away_slg = fnum(lineup.get("away_lineup_slg_proxy"), 0.400)
            home_strength = fnum(lineup.get("home_lineup_strength_score"), 50)
            away_strength = fnum(lineup.get("away_lineup_strength_score"), 50)

            idx = ((home_obp + away_obp - 0.630) * 100) + ((home_slg + away_slg - 0.800) * 50) + ((home_strength + away_strength - 100) / 10)
            x["battingOverSupportIndex"] = round(idx, 3)
            x["battingContextSignal"] = "OVER_SUPPORT" if idx >= 5 else "OVER_CAUTION" if idx <= -5 else "NEUTRAL"
        else:
            x["battingOverSupportIndex"] = ""
            x["battingContextSignal"] = "NO_MATCH"

        enriched.append(x)

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_batting_context_only",
        "rules": {
            "liveTelegram": "unchanged",
            "purpose": "Merge lineup OBP/SLG proxies into O/U V2 strict paper candidates.",
            "note": "Lineup proxy fields, not official BaseballPred OBP_162/SLG_162."
        },
        "counts": {
            "candidates": len(candidates),
            "lineupRows": len(lineup_rows),
            "matched": matched,
            "notMatched": len(candidates) - matched,
            "overSupport": sum(1 for x in enriched if x.get("battingContextSignal") == "OVER_SUPPORT"),
            "overCaution": sum(1 for x in enriched if x.get("battingContextSignal") == "OVER_CAUTION"),
        },
        "candidates": enriched,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 159 MERGE LINEUP OBP/SLG PROXY INTO O/U V2",
        "=" * 74,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Uses mlb_lineup_player_features.csv OBP/SLG proxy fields.",
        "",
        f"Input: {INPUT_JSON}",
        f"Lineup CSV: {LINEUP_CSV}",
        f"Output: {OUT_JSON}",
        "",
        "Counts:",
        f"- candidates: {out['counts']['candidates']}",
        f"- lineup rows: {out['counts']['lineupRows']}",
        f"- matched: {out['counts']['matched']}",
        f"- not matched: {out['counts']['notMatched']}",
        f"- over support: {out['counts']['overSupport']}",
        f"- over caution: {out['counts']['overCaution']}",
        "",
        "Top candidates:",
    ]
    for x in enriched[:12]:
        lines.append(
            f"- {x.get('strictV2Grade')} | {x.get('game')} | {x.get('pick')} | "
            f"Matched={x.get('battingContextMatched')} | Signal={x.get('battingContextSignal')} | "
            f"BattingIndex={x.get('battingOverSupportIndex')} | "
            f"HomeOBP={x.get('home_lineup_obp_proxy','')} AwayOBP={x.get('away_lineup_obp_proxy','')}"
        )

    lines += ["", "Decision:", "- Use batting context to refine V2 paper score only.", "- Keep 136 live unchanged until paper test wins."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
