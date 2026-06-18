from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, urllib.request, re

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
LEDGER = ASTRO / "ASTRODDS-client-lean-ledger.json"
REPORT = REPORTS / "509_resolve_client_lean_results_from_mlb_report.txt"

def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception: return default

def save(path, obj): path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def norm(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def fetch_schedule(date_yyyy_mm_dd):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_yyyy_mm_dd}&hydrate=team,linescore"
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def candidate_dates():
    now = datetime.now(timezone.utc)
    return sorted({(now + timedelta(days=d)).strftime("%Y-%m-%d") for d in [-1,0,1]})

def main():
    ledger = load(LEDGER, {"clientLeans": []}); rows = ledger.get("clientLeans", []) or []
    pending = [r for r in rows if r.get("status") == "PENDING"]
    schedule_games = []
    for d in candidate_dates():
        try:
            data = fetch_schedule(d)
            for date_block in data.get("dates", []):
                for g in date_block.get("games", []):
                    teams = g.get("teams", {})
                    away = ((teams.get("away") or {}).get("team") or {}).get("name", "")
                    home = ((teams.get("home") or {}).get("team") or {}).get("name", "")
                    schedule_games.append({
                        "game": f"{away} @ {home}", "away": away, "home": home,
                        "awayScore": (teams.get("away") or {}).get("score"),
                        "homeScore": (teams.get("home") or {}).get("score"),
                        "status": (g.get("status") or {}).get("detailedState", ""),
                        "gamePk": g.get("gamePk"), "date": d
                    })
        except Exception:
            pass
    settled, still_pending, not_found = [], [], []
    for r in pending:
        match = next((g for g in schedule_games if norm(g.get("game")) == norm(r.get("game"))), None)
        if not match:
            not_found.append(r); continue
        status_l = str(match.get("status", "")).lower()
        r["mlbStatus"] = match.get("status"); r["gamePk"] = match.get("gamePk")
        if not ("final" in status_l or "game over" in status_l):
            still_pending.append(r); continue
        away_score, home_score = match.get("awayScore"), match.get("homeScore")
        winner = None
        if away_score is not None and home_score is not None:
            if int(away_score) > int(home_score): winner = match.get("away")
            elif int(home_score) > int(away_score): winner = match.get("home")
        r["awayScore"] = away_score; r["homeScore"] = home_score; r["winner"] = winner; r["settledAtUTC"] = datetime.now(timezone.utc).isoformat()
        if winner and norm(winner) == norm(r.get("pick")):
            r["status"] = "SETTLED"; r["result"] = "WIN"
        elif winner:
            r["status"] = "SETTLED"; r["result"] = "LOSS"
        settled.append(r)
    ledger["updatedAt"] = datetime.now(timezone.utc).isoformat(); save(LEDGER, ledger)
    lines = ["ASTRODDS 509 RESOLVE CLIENT LEAN RESULTS FROM MLB", "="*78, f"Generated UTC: {datetime.now(timezone.utc).isoformat()}", "", f"Ledger rows: {len(rows)}", f"Pending input rows: {len(pending)}", f"Settled now: {len(settled)}", f"Still pending: {len(still_pending)}", f"Not found: {len(not_found)}", "", "Settled:"]
    lines += [f"- {r.get('result')} | {r.get('pick')} ML | {r.get('game')} | score={r.get('awayScore')}-{r.get('homeScore')} | winner={r.get('winner')}" for r in settled] or ["- none"]
    lines += ["", "Still pending:"] + ([f"- {r.get('pick')} ML | {r.get('game')} | MLB status={r.get('mlbStatus')}" for r in still_pending] or ["- none"])
    if not_found:
        lines += ["", "Not found:"] + [f"- {r.get('pick')} ML | {r.get('game')}" for r in not_found]
    lines += ["", f"Ledger: {LEDGER}", "Rule: only settle when MLB status is Final/Game Over."]
    REPORT.write_text("\n".join(lines), encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
