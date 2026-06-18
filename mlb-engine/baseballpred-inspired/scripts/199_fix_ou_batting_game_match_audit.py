from pathlib import Path
from datetime import datetime, timezone
import csv,json,re
ROOT=Path(__file__).resolve().parents[3]
ASTRO=ROOT/".astrodds"; REPORTS=ROOT/"mlb-engine"/"baseballpred-inspired"/"reports"; PROCESSED=ROOT/"mlb-engine"/"data"/"processed"
REPORT=REPORTS/"199_fix_ou_batting_game_match_audit_report.txt"; OUT_JSON=ASTRO/"ASTRODDS-ou-batting-match-audit-latest.json"
ALIASES={"athletics":"athletics","oakland athletics":"athletics","sacramento athletics":"athletics","st louis cardinals":"st louis cardinals","st. louis cardinals":"st louis cardinals","la dodgers":"los angeles dodgers","los angeles dodgers":"los angeles dodgers","la angels":"los angeles angels","los angeles angels":"los angeles angels","ny yankees":"new york yankees","new york yankees":"new york yankees","ny mets":"new york mets","new york mets":"new york mets"}
def norm(s):
    s=str(s or "").lower().strip().replace(".",""); s=re.sub(r"[^a-z0-9]+"," ",s); s=re.sub(r"\s+"," ",s).strip(); return ALIASES.get(s,s)
def parse_game(g):
    g=str(g or "")
    for sep in [" @ "," vs. "," vs "]:
        if sep in g:
            a,h=g.split(sep,1); return norm(a),norm(h)
    return "",""
def gkey(game="",away="",home=""):
    if game and (not away or not home): away,home=parse_game(game)
    return f"{norm(away)}@{norm(home)}" if away and home else norm(game)
def read_csv(p):
    if not p.exists(): return []
    with p.open("r",encoding="utf-8-sig",errors="ignore",newline="") as f: return list(csv.DictReader(f))
def load(p):
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}
def flat(o):
    out=[]
    if isinstance(o,list):
        for x in o: out+=flat(x)
    elif isinstance(o,dict):
        pick=str(o.get("pick",o.get("Pick",""))).lower()
        if ("over" in pick or "under" in pick) and (o.get("game") or o.get("Game")): out.append(o)
        for v in o.values(): out+=flat(v)
    return out
def main():
    REPORTS.mkdir(parents=True,exist_ok=True); ASTRO.mkdir(parents=True,exist_ok=True)
    ou=flat(load(ASTRO/"ASTRODDS-ou-v2-batting-context-score-latest.json"))
    sources=[ASTRO/"ASTRODDS-full-slate-context-final-latest.csv",PROCESSED/"mlb_lineup_player_features.csv",PROCESSED/"mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv",PROCESSED/"mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv"]
    idx={}; total=0
    for src in sources:
        rows=read_csv(src); total+=len(rows)
        for r in rows:
            game=r.get("game") or r.get("Game") or ""; away=r.get("awayTeam") or r.get("away_team") or r.get("away"); home=r.get("homeTeam") or r.get("home_team") or r.get("home")
            k=gkey(game,away,home)
            if k and k not in idx: idx[k]={"source":str(src),"row":r}
    matched=[]; unmatched=[]
    for r in ou:
        game=r.get("game") or r.get("Game") or ""; k=gkey(game); m=idx.get(k)
        row={"game":game,"pick":r.get("pick") or r.get("Pick"),"line":r.get("line") or r.get("Line"),"key":k}
        if m: row["source"]=m["source"]; matched.append(row)
        else: unmatched.append(row)
    out={"generatedAt":datetime.now(timezone.utc).isoformat(),"ouCandidates":len(ou),"lineupRowsIndexed":total,"matchedCount":len(matched),"unmatchedCount":len(unmatched),"matchedPreview":matched[:30],"unmatchedPreview":unmatched[:30],"recommendation":"If unmatched remains high, patch source game/team normalization in O/U batting context score script."}
    OUT_JSON.write_text(json.dumps(out,indent=2),encoding="utf-8")
    lines=["ASTRODDS 199 FIX O/U BATTING GAME MATCH AUDIT","="*72,f"Generated UTC: {out['generatedAt']}","",f"Total O/U candidates: {len(ou)}",f"Lineup rows indexed: {total}",f"Matched count: {len(matched)}",f"No-match count: {len(unmatched)}","","Matched preview:"]
    for m in matched[:20]: lines.append(f"- {m['game']} | {m['pick']} | line={m['line']} | source={Path(m['source']).name}")
    lines+=["","Still unmatched:"]
    for u in unmatched[:20]: lines.append(f"- {u['game']} | {u['pick']} | line={u['line']} | key={u['key']}")
    lines+=["","Recommendation:",f"- {out['recommendation']}",f"JSON: {OUT_JSON}"]
    REPORT.write_text("\n".join(lines),encoding="utf-8"); print("\n".join(lines))
if __name__=="__main__": main()
