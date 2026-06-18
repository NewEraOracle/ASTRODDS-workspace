from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"

BOARD_JSON = ASTRO / "ASTRODDS-moneyline-only-today-board-latest.json"
OUT_JSON = ASTRO / "ASTRODDS-moneyline-live-status-fixed-latest.json"
REPORT = REPORTS / "226_moneyline_live_status_eligibility_fix_report.txt"

STATUS_ORDER = {"OFFICIAL": 0, "A_PAPER": 1, "REVIEW": 2, "WATCH": 3, "BLOCKED": 4, "NO_BET": 5}

TEAM_ALIASES = {
    "athletics": "Athletics",
    "oakland athletics": "Athletics",
    "sacramento athletics": "Athletics",
    "st louis cardinals": "St. Louis Cardinals",
    "st. louis cardinals": "St. Louis Cardinals",
    "ny yankees": "New York Yankees",
    "new york yankees": "New York Yankees",
    "ny mets": "New York Mets",
    "new york mets": "New York Mets",
    "la dodgers": "Los Angeles Dodgers",
    "los angeles dodgers": "Los Angeles Dodgers",
    "la angels": "Los Angeles Angels",
    "los angeles angels": "Los Angeles Angels",
}

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def canon(s):
    raw = str(s or "").strip()
    return TEAM_ALIASES.get(norm(raw), raw)

def parse_game(game):
    g = str(game or "").strip()
    for sep in [" @ ", " vs. ", " vs "]:
        if sep in g:
            a, h = g.split(sep, 1)
            return canon(a), canon(h)
    return "", ""

def game_key(game="", away="", home=""):
    if game and (not away or not home):
        away, home = parse_game(game)
    if away and home:
        return f"{norm(canon(away))}@{norm(canon(home))}"
    return norm(game)

def fnum(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%", "").replace("+", "").replace(",", ".")
    if not s:
        return default
    try:
        return float(s)
    except Exception:
        return default

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fetch_statsapi_status():
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"
    idx = {}
    errors = []

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return idx, [f"StatsAPI fetch failed: {type(e).__name__}: {e}"], today

    for d in data.get("dates", []):
        for g in d.get("games", []):
            away = (((g.get("teams") or {}).get("away") or {}).get("team") or {}).get("name", "")
            home = (((g.get("teams") or {}).get("home") or {}).get("team") or {}).get("name", "")
            status = (g.get("status") or {}).get("detailedState", "") or (g.get("status") or {}).get("abstractGameState", "")
            abstract = (g.get("status") or {}).get("abstractGameState", "")
            coded = (g.get("status") or {}).get("codedGameState", "")
            game_date = g.get("gameDate", "")
            key = game_key("", away, home)
            if key:
                idx[key] = {
                    "awayTeam": away,
                    "homeTeam": home,
                    "game": f"{away} @ {home}",
                    "liveStatus": status,
                    "abstractStatus": abstract,
                    "codedGameState": coded,
                    "gameDate": game_date,
                    "gamePk": g.get("gamePk", ""),
                }
    return idx, errors, today

def is_live_blocked(status_info):
    if not status_info:
        return None

    status = str(status_info.get("liveStatus", "")).lower()
    abstract = str(status_info.get("abstractStatus", "")).lower()
    coded = str(status_info.get("codedGameState", "")).lower()

    # MLB StatsAPI verified states only.
    if "final" in status or abstract == "final":
        return True
    if "in progress" in status or abstract == "live":
        return True
    if "delayed" in status or "postponed" in status or "suspended" in status:
        return True

    # Pregame/scheduled/warmup are NOT blocked.
    if "scheduled" in status or "pre-game" in status or "pregame" in status or "warmup" in status:
        return False
    if abstract == "preview":
        return False

    # Unknown -> do not false-block.
    return False

def tier_from_edge(edge):
    if edge is None:
        return "NO_BET"
    if edge >= 12:
        return "A_PICK"
    if edge >= 8:
        return "VALUE_LEAN"
    if edge >= 5:
        return "ACTION_LEAN"
    return "NO_BET"

def board_status_from_action(action):
    if action == "A_PICK":
        return "REVIEW"  # Dashboard only; Telegram/live official gate unchanged.
    if action == "VALUE_LEAN":
        return "REVIEW"
    if action == "ACTION_LEAN":
        return "WATCH"
    return "NO_BET"

def main():
    ASTRO.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = load_json(BOARD_JSON)
    rows = data.get("moneylineBoard", []) if isinstance(data, dict) else []

    status_idx, errors, statsapi_date = fetch_statsapi_status()

    fixed_false_blocks = 0
    verified_blocked = 0
    verified_open = 0
    no_live_match = 0
    actionable = 0

    for r in rows:
        game = r.get("game", "")
        away = r.get("awayTeam", "")
        home = r.get("homeTeam", "")
        key = game_key(game, away, home)
        live = status_idx.get(key)

        # Keep stale/candidate status for audit, but do not use it for blocking anymore.
        if "cachedMlbStatus" not in r:
            r["cachedMlbStatus"] = r.get("mlbStatus", "")
        if "cachedCandidateReasons" not in r:
            r["cachedCandidateReasons"] = r.get("candidateReasons", "")

        edge = fnum(r.get("currentEdgePct", r.get("edgePct")), None)
        model = fnum(r.get("modelProbability"), None)
        price = fnum(r.get("price"), None)

        if live:
            is_block = is_live_blocked(live)
            r["liveMlbStatus"] = live.get("liveStatus", "")
            r["mlbStatus"] = live.get("liveStatus", "")
            r["liveGameDate"] = live.get("gameDate", "")
            r["liveGamePk"] = live.get("gamePk", "")
            r["liveStatusSource"] = "MLB StatsAPI current schedule"
        else:
            is_block = None
            r["liveMlbStatus"] = ""
            r["liveStatusSource"] = "NO_LIVE_MATCH_DO_NOT_FALSE_BLOCK"
            no_live_match += 1

        if is_block is True:
            verified_blocked += 1
            r["status"] = "BLOCKED"
            r["actionStatus"] = "BLOCKED_STARTED_OR_FINAL"
            r["telegramEligible"] = False
            r["mainReason"] = "Verified by live MLB schedule: game is already started/final/delayed."
            r["riskReason"] = f"Live MLB status={r.get('liveMlbStatus')}. No betting after start."
        else:
            if str(r.get("status", "")).upper() == "BLOCKED":
                fixed_false_blocks += 1

            # Remove stale blocker text so 222 does not re-block from cached 292 reasons.
            r["candidateReasons"] = str(r.get("candidateReasons", "")).replace("already_started_or_final", "cached_candidate_status_ignored")
            r["riskReason"] = str(r.get("riskReason", "")).replace("already_started_or_final", "cached_candidate_status_ignored")
            if "game is already started" in str(r.get("mainReason", "")).lower():
                r["mainReason"] = "Live MLB schedule does not confirm started/final; stale block removed."

            if model is not None and price is not None and edge is None:
                edge = round((model - price) * 100, 2)
                r["currentEdgePct"] = edge
                r["edgePct"] = edge

            action = tier_from_edge(edge)
            r["actionStatus"] = action
            r["status"] = board_status_from_action(action)
            r["telegramEligible"] = False

            if action != "NO_BET":
                actionable += 1
                r["mainReason"] = "Pregame/live-open Moneyline value candidate after live status verification."
                r["riskReason"] = f"Current edge {edge}% from model {round(model*100,1) if model is not None else ''}% vs market {round(price*100,1) if price is not None else ''}%. Dashboard/manual only."
            else:
                if model is None or price is None:
                    r["mainReason"] = "Live status open, but model or price is missing."
                    r["riskReason"] = "No actionable Moneyline without both modelProbability and market price."
                else:
                    r["mainReason"] = "Live status open, but no positive enough current edge."
                    r["riskReason"] = f"Current edge {edge}%."
            verified_open += 1

    rows.sort(key=lambda x: (STATUS_ORDER.get(x.get("status", "NO_BET"), 9), -fnum(x.get("currentEdgePct", x.get("edgePct")), -999), -fnum(x.get("baseballPredScore"), 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    counts = {}
    for r in rows:
        counts[r.get("status", "NO_BET")] = counts.get(r.get("status", "NO_BET"), 0) + 1

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "statsapiDate": statsapi_date,
        "rows": len(rows),
        "liveStatusRows": len(status_idx),
        "fixedFalseBlocks": fixed_false_blocks,
        "verifiedBlockedRows": verified_blocked,
        "verifiedOpenRows": verified_open,
        "noLiveMatchRows": no_live_match,
        "actionableAfterLiveStatus": actionable,
        "errors": errors,
        "counts": counts,
        "moneylineBoard": rows,
        "rule": "Only live MLB StatsAPI current schedule can block a Moneyline as started/final. Cached 292 status is audit-only.",
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    BOARD_JSON.write_text(json.dumps({
        "generatedAt": out["generatedAt"],
        "moneylineRows": len(rows),
        "counts": counts,
        "moneylineBoard": rows,
        "rule": out["rule"],
    }, indent=2), encoding="utf-8")

    lines = [
        "ASTRODDS 226 MONEYLINE LIVE STATUS ELIGIBILITY FIX",
        "=" * 76,
        f"Generated UTC: {out['generatedAt']}",
        f"StatsAPI date: {out['statsapiDate']}",
        "",
        f"Rows: {out['rows']}",
        f"Live status rows: {out['liveStatusRows']}",
        f"Fixed false blocks: {out['fixedFalseBlocks']}",
        f"Verified blocked rows: {out['verifiedBlockedRows']}",
        f"Verified open rows: {out['verifiedOpenRows']}",
        f"No live match rows: {out['noLiveMatchRows']}",
        f"Actionable after live status: {out['actionableAfterLiveStatus']}",
        "",
        "Counts:",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    if errors:
        lines += ["", "Errors:"]
        for e in errors:
            lines.append(f"- {e}")

    lines += ["", "Top Moneyline after live status fix:"]
    for r in rows[:80]:
        lines.append(
            f"- #{r['rank']} | {r.get('status')} | action={r.get('actionStatus','')} | {r.get('pick')} | {r.get('game')} | "
            f"price={r.get('price')} | model={r.get('modelProbability')} | edge={r.get('currentEdgePct', r.get('edgePct'))} | "
            f"liveStatus={r.get('liveMlbStatus','')} | cachedStatus={r.get('cachedMlbStatus','')} | {r.get('mainReason')}"
        )

    lines += ["", f"JSON: {OUT_JSON}", "Rule: Cached candidate status can never block by itself."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
