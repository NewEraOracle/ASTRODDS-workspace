from pathlib import Path
from datetime import datetime, timezone
import csv, json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

FILTER_JSON = ASTRO / "ASTRODDS-moneyline-authoritative-schedule-filter-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-price-source-trace-latest.json"
REPORT = REPORTS / "243_trace_missing_official_moneyline_prices_report.txt"

SEARCH_EXTS = {".json", ".csv", ".txt"}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}

def read_text_lite(path, max_bytes=2_000_000):
    try:
        with path.open("rb") as f:
            b = f.read(max_bytes)
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    data = load_json(FILTER_JSON)
    missing = data.get("missingOfficialGames", []) or []

    # Also trace all official games, not just missing.
    official = []
    for g in data.get("missingOfficialGames", []) or []:
        official.append(g.get("officialGame", ""))
    for r in data.get("keptMoneylineBoard", []) or []:
        if r.get("game") and r.get("game") not in official:
            official.append(r.get("game"))

    # Hard focus from latest report.
    focus_games = [g.get("officialGame","") for g in missing]
    focus_teams = []
    for game in focus_games:
        parts = re.split(r"\s+@\s+", game)
        if len(parts) == 2:
            focus_teams.extend(parts)
    focus_terms = sorted(set([t for t in focus_teams if t]))

    candidates = []
    for p in ASTRO.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SEARCH_EXTS:
            continue
        if p.stat().st_size > 8_000_000:
            continue
        candidates.append(p)

    hits = []
    for p in candidates:
        text = read_text_lite(p)
        if not text:
            continue
        low = norm(text)
        team_hits = [team for team in focus_terms if norm(team) in low]
        game_hits = [game for game in focus_games if norm(game.replace("@", " ")) in low or all(norm(x) in low for x in re.split(r"\s+@\s+", game))]
        if team_hits or game_hits:
            hits.append({
                "file": str(p),
                "size": p.stat().st_size,
                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "teamHits": team_hits,
                "gameHits": game_hits,
            })

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "missingOfficialGames": missing,
        "focusTerms": focus_terms,
        "searchedFiles": len(candidates),
        "hitFiles": hits,
        "rule": "If a missing official game is not found in raw .astrodds files, the odds source did not collect it. If found, matcher/normalizer is the issue.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 243 TRACE MISSING OFFICIAL MONEYLINE PRICES",
        "=" * 78,
        f"Generated UTC: {out['generatedAt']}",
        "",
        "Missing official games being traced:",
    ]
    if missing:
        for g in missing:
            lines.append(f"- {g.get('officialGame')} | {g.get('liveMlbStatus')} | {g.get('gameDate')} | gamePk={g.get('gamePk')}")
    else:
        lines.append("- none")

    lines += [
        "",
        f"Files searched in .astrodds: {out['searchedFiles']}",
        f"Files with team/game hits: {len(hits)}",
        "",
        "Hit files:",
    ]

    if hits:
        for h in hits[:80]:
            lines.append(f"- {h['file']} | hits teams={h['teamHits']} games={h['gameHits']} | modified={h['modified']} | size={h['size']}")
    else:
        lines.append("- none")

    lines += [
        "",
        "Interpretation:",
        "- If Angels/Athletics/Mets/Phillies/Cardinals/Royals do not appear in raw price files, the collector source missed them.",
        "- If they appear in raw files but not in the final moneyline board, the matcher is broken.",
        "",
        f"JSON: {OUT_JSON}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
