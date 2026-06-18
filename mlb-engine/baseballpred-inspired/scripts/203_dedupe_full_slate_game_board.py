from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

IN_JSON = ASTRO / "ASTRODDS-full-slate-game-board-moneyline-expanded-latest.json"
FALLBACK_JSON = ASTRO / "ASTRODDS-full-slate-game-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-full-slate-game-board-clean-latest.json"
REPORT = REPORTS / "203_dedupe_full_slate_game_board_report.txt"

STATUS_ORDER = {"OFFICIAL":0, "A_PAPER":1, "REVIEW":2, "WATCH":3, "BLOCKED":4, "NO_BET":5}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fnum(v, default=0):
    try:
        s = str(v).strip().replace("+", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default

def dedupe_key(r):
    # One visible row per game + market + pick + line/price.
    return (
        norm(r.get("game")),
        norm(r.get("marketType")),
        norm(r.get("pick")),
        norm(r.get("line") or r.get("price") or ""),
    )

def better(a, b):
    # Lower status order wins, then higher score.
    ao = STATUS_ORDER.get(a.get("status", "NO_BET"), 9)
    bo = STATUS_ORDER.get(b.get("status", "NO_BET"), 9)
    if ao != bo:
        return a if ao < bo else b
    return a if fnum(a.get("baseballPredScore"), 0) >= fnum(b.get("baseballPredScore"), 0) else b

def merge_sources(a, b):
    src = []
    for x in (a.get("sourceFilesUsed") or []) + (b.get("sourceFilesUsed") or []):
        if x not in src:
            src.append(x)
    a["sourceFilesUsed"] = src
    return a

def main():
    data = load(IN_JSON)
    if not data:
        data = load(FALLBACK_JSON)
    rows = data.get("gameBoard", []) if isinstance(data, dict) else []

    bykey = {}
    duplicates = 0

    for r in rows:
        key = dedupe_key(r)
        if key in bykey:
            duplicates += 1
            chosen = better(bykey[key], r)
            other = r if chosen is bykey[key] else bykey[key]
            bykey[key] = merge_sources(chosen, other)
        else:
            bykey[key] = r

    clean = list(bykey.values())
    clean.sort(key=lambda r: (STATUS_ORDER.get(r.get("status", "NO_BET"), 9), -fnum(r.get("baseballPredScore"), 0)))
    for i, r in enumerate(clean, 1):
        r["rank"] = i

    counts = {}
    for r in clean:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rowsBefore": len(rows),
        "rowsAfter": len(clean),
        "duplicatesRemoved": duplicates,
        "counts": counts,
        "summary": {
            "official": counts.get("OFFICIAL", 0),
            "aPaper": counts.get("A_PAPER", 0),
            "review": counts.get("REVIEW", 0),
            "watch": counts.get("WATCH", 0),
            "blockedNoBet": counts.get("BLOCKED", 0) + counts.get("NO_BET", 0),
            "moneylineRows": sum(1 for r in clean if r.get("marketType") == "MONEYLINE"),
            "ouRows": sum(1 for r in clean if r.get("marketType") == "OU"),
            "telegramEligible": sum(1 for r in clean if r.get("telegramEligible")),
        },
        "gameBoard": clean,
        "rule": "Dashboard only. Dedupe display board.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 203 DEDUPE FULL SLATE GAME BOARD",
        "=" * 68,
        f"Generated UTC: {out['generatedAt']}",
        "",
        f"Rows before: {out['rowsBefore']}",
        f"Rows after: {out['rowsAfter']}",
        f"Duplicates removed: {out['duplicatesRemoved']}",
        "",
        "Summary:",
    ]
    for k, v in out["summary"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "Top clean rows:"]
    for r in clean[:45]:
        lp = r.get("line") or r.get("price") or ""
        edge = r.get("edgePct") or r.get("edgeRuns") or ""
        lines.append(f"- #{r['rank']} | {r.get('status')} | {r.get('marketType')} | {r.get('pick')} | {r.get('game')} | line/price={lp} | score={r.get('baseballPredScore')} | edge={edge} | telegram={r.get('telegramEligible')}")
    lines += ["", f"JSON: {OUT_JSON}", "Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
