from pathlib import Path
from datetime import datetime
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
PROCESSED = ROOT / "mlb-engine" / "data" / "processed"

OU_V2 = ASTRO / "ASTRODDS-ou-v2-baseballpred-sidecar-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-ou-live-context-enrichment-latest.json"
REPORT = REPORTS / "151_ou_live_context_enrichment_audit_report.txt"

SOURCES = {
    "pitcher": [
        ASTRO / "ASTRODDS-advanced-pitcher-team-metrics-latest.csv",
        ASTRO / "VVS-pitcher-context-latest.csv",
        PROCESSED / "mlb_moneyline_features_with_pitchers.csv",
    ],
    "bullpen": [
        ASTRO / "VVS-bullpen-context-latest.csv",
        PROCESSED / "mlb_bullpen_features.csv",
        PROCESSED / "mlb_moneyline_features_with_bullpen.csv",
    ],
    "weather_lineup": [
        PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",
        PROCESSED / "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv",
        PROCESSED / "mlb_lineup_player_features.csv",
    ],
}

def norm(s):
    s = str(s or "").lower().strip()
    s = s.replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    aliases = {
        "blue jays": "toronto blue jays",
        "red sox": "boston red sox",
        "orioles": "baltimore orioles",
        "mariners": "seattle mariners",
        "white sox": "chicago white sox",
        "yankees": "new york yankees",
        "guardians": "cleveland guardians",
        "brewers": "milwaukee brewers",
        "royals": "kansas city royals",
        "nationals": "washington nationals",
        "tigers": "detroit tigers",
        "astros": "houston astros",
        "athletics": "athletics",
        "oakland athletics": "athletics",
    }
    return aliases.get(s, s)

def parse_game(game):
    g = str(game or "")
    for sep in [" vs. ", " vs ", " @ "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return norm(a), norm(h)
    return "", ""

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def read_csv(path, max_rows=50000):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            rows = list(csv.DictReader(f))
            return rows[-max_rows:] if len(rows) > max_rows else rows
    except Exception:
        return []

def row_text(row):
    return " ".join(str(v) for v in row.values())

def row_has_game(row, away, home):
    text = norm(row_text(row))
    return away and home and away in text and home in text

def find_context_rows(away, home, source_paths, limit=3):
    hits = []
    for path in source_paths:
        rows = read_csv(path)
        for r in rows:
            if row_has_game(r, away, home):
                hits.append({"source": str(path), "row": r})
                if len(hits) >= limit:
                    return hits
    return hits

def numeric_from_row(row, keys):
    vals = {}
    for k, v in row.items():
        kl = str(k).lower()
        for wanted in keys:
            if wanted in kl:
                vals[k] = v
    return vals

def summarize_hits(hits, kind):
    if not hits:
        return {"available": False, "source": "", "signals": {}}

    row = hits[0]["row"]
    if kind == "pitcher":
        keys = ["pitcher", "quality", "score", "era", "whip", "so", "strike", "starter"]
    elif kind == "bullpen":
        keys = ["bullpen", "fatigue", "score", "games", "ip", "reliever", "whip"]
    else:
        keys = ["weather", "wind", "temp", "park", "lineup", "injury", "missing", "top4", "status"]

    return {
        "available": True,
        "source": hits[0]["source"],
        "signals": numeric_from_row(row, keys),
    }

def risk_adjustment(pitcher, bullpen, weather_lineup):
    flags = []
    adj = 0.0

    # Very conservative audit-only adjustment.
    # We do not change live picks here.
    for source in [pitcher, bullpen, weather_lineup]:
        sig = " ".join(f"{k}={v}" for k, v in source.get("signals", {}).items()).lower()
        if "missing" in sig or "injury" in sig:
            flags.append("lineup/injury context present")
        if "fatigue" in sig and ("high" in sig or "warning" in sig):
            flags.append("bullpen fatigue context present")
            adj += 0.10
        if "weather" in sig or "wind" in sig or "temp" in sig:
            flags.append("weather/park context present")
    return adj, sorted(set(flags))

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    ASTRO.mkdir(parents=True, exist_ok=True)

    data = read_json(OU_V2, {})
    candidates = data.get("candidates", []) if isinstance(data, dict) else []

    enriched = []
    for c in candidates:
        game = c.get("game", "")
        away, home = parse_game(game)

        pitcher_hits = find_context_rows(away, home, SOURCES["pitcher"])
        bullpen_hits = find_context_rows(away, home, SOURCES["bullpen"])
        weather_hits = find_context_rows(away, home, SOURCES["weather_lineup"])

        pitcher = summarize_hits(pitcher_hits, "pitcher")
        bullpen = summarize_hits(bullpen_hits, "bullpen")
        weather_lineup = summarize_hits(weather_hits, "weather_lineup")
        adj, flags = risk_adjustment(pitcher, bullpen, weather_lineup)

        grade = c.get("gradeV2", "")
        edge = float(c.get("edgeRuns", 0) or 0)
        context_ready = pitcher["available"] or bullpen["available"] or weather_lineup["available"]

        # Still sidecar only. Upgrade recommendation only if base is A+ and context exists.
        recommendation = "KEEP_CURRENT"
        if grade == "A+" and context_ready:
            recommendation = "A_PLUS_CONTEXT_CONFIRMED"
        elif grade == "A+" and not context_ready:
            recommendation = "A_PLUS_NO_EXTRA_CONTEXT"

        enriched.append({
            **c,
            "awayNorm": away,
            "homeNorm": home,
            "contextReady": context_ready,
            "pitcherContext": pitcher,
            "bullpenContext": bullpen,
            "weatherLineupContext": weather_lineup,
            "contextFlags": flags,
            "edgeRunsContextAdjustmentAuditOnly": round(adj, 2),
            "recommendationAuditOnly": recommendation,
        })

    out = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "mode": "sidecar_context_enrichment_only",
        "rules": {
            "liveChange": "none",
            "purpose": "Attach pitcher/bullpen/weather/lineup context to O/U V2 candidates for audit.",
            "doNotMerge": "Do not replace 136 until backtested with true lines.",
        },
        "counts": {
            "candidates": len(enriched),
            "contextReady": sum(1 for x in enriched if x["contextReady"]),
            "aPlusContextConfirmed": sum(1 for x in enriched if x["recommendationAuditOnly"] == "A_PLUS_CONTEXT_CONFIRMED"),
            "aPlusNoExtraContext": sum(1 for x in enriched if x["recommendationAuditOnly"] == "A_PLUS_NO_EXTRA_CONTEXT"),
        },
        "candidates": enriched,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 151 O/U LIVE CONTEXT ENRICHMENT AUDIT",
        "=" * 70,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Rules:",
        "- Sidecar only.",
        "- Does not touch live Telegram.",
        "- Adds available pitcher/bullpen/weather/lineup context to O/U V2 candidates.",
        "",
        f"Input: {OU_V2}",
        f"Output: {OUT_JSON}",
        "",
        "Counts:",
        f"- candidates: {out['counts']['candidates']}",
        f"- contextReady: {out['counts']['contextReady']}",
        f"- A+ context confirmed: {out['counts']['aPlusContextConfirmed']}",
        f"- A+ no extra context: {out['counts']['aPlusNoExtraContext']}",
        "",
        "Top candidates:",
    ]

    for x in enriched[:12]:
        lines.append(
            f"- {x.get('recommendationAuditOnly')} | {x.get('gradeV2')} | {x.get('game')} | {x.get('pick')} | "
            f"EdgeRuns=+{float(x.get('edgeRuns',0) or 0):.2f} | ContextReady={x.get('contextReady')} | "
            f"Flags={','.join(x.get('contextFlags', [])) if x.get('contextFlags') else 'none'}"
        )

    lines += [
        "",
        "Decision:",
        "- Keep 136 live unchanged.",
        "- Use this report to see whether O/U A+ picks have supporting context.",
        "- Next: 152 can convert context into stricter V2 paper-only score.",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
