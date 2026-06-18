from pathlib import Path
from datetime import datetime, timezone
import csv, json, re, math

ROOT = Path(__file__).resolve().parents[3]
ASTRO = ROOT / ".astrodds"
REPORTS = ROOT / "mlb-engine" / "baseballpred-inspired" / "reports"
OUT_JSON = ASTRO / "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
REPORT = REPORTS / "198_baseballpred_full_slate_ranker_report.txt"

ALIASES = {
    "athletics":"Athletics","oakland athletics":"Athletics","sacramento athletics":"Athletics",
    "st louis cardinals":"St. Louis Cardinals","st. louis cardinals":"St. Louis Cardinals",
    "la dodgers":"Los Angeles Dodgers","los angeles dodgers":"Los Angeles Dodgers",
    "la angels":"Los Angeles Angels","los angeles angels":"Los Angeles Angels",
    "ny yankees":"New York Yankees","new york yankees":"New York Yankees",
    "ny mets":"New York Mets","new york mets":"New York Mets",
}
LINE_KEYS = ["line","Line","totalLine","total_line","point","Point","ouLine","marketLine"]
PRICE_KEYS = ["price","Price","marketPrice","Market","market","entry","Entry","close_price"]

def nk(s):
    s = str(s or "").lower().strip().replace(".", "")
    s = re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def ct(s):
    raw = str(s or "").strip()
    return ALIASES.get(nk(raw), raw)

def tk(s): return nk(ct(s))

def parse_game(game):
    g = str(game or "").strip()
    for sep in [" @ "," vs. "," vs "]:
        if sep in g:
            a,h = g.split(sep,1)
            return ct(a), ct(h)
    return "", ""

def gkey(game="", away="", home=""):
    if game and (not away or not home):
        away, home = parse_game(game)
    return f"{tk(away)}@{tk(home)}" if away and home else nk(game)

def fnum(v, default=None):
    try:
        s = str(v).strip().replace("%","").replace("+","")
        if not s: return default
        return float(s)
    except Exception: return default

def is_half(v):
    x = fnum(v, None)
    if x is None: return False
    return abs(abs(x - math.floor(x)) - 0.5) < 1e-9

def read_csv(path):
    if not path.exists(): return []
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def load_json(path):
    if not path.exists(): return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def flatten(obj):
    out=[]
    if isinstance(obj,list):
        for x in obj: out += flatten(x)
    elif isinstance(obj,dict):
        if (obj.get("game") or obj.get("Game") or obj.get("matchup")) and any(k in obj for k in ["pick","Pick","decision","grade","score","edgeRuns","edge_runs"]):
            out.append(obj)
        for v in obj.values(): out += flatten(v)
    return out

def fv(row, keys, default=""):
    for k in keys:
        if isinstance(row,dict) and k in row and str(row.get(k,"")).strip()!="":
            return row.get(k)
    return default

def get_line(row): return fv(row, LINE_KEYS, "")
def get_price(row): return fv(row, PRICE_KEYS, "")

def status_rank(s):
    return {"OFFICIAL":0,"A_PAPER":1,"REVIEW":2,"WATCH":3,"BLOCKED":4,"NO_BET":5}.get(s,9)

def infer_status(grade="", decision="", score=None, official=False):
    text = f"{grade} {decision}".upper()
    if official or "A PICK" in text or "ENGINE_BUY" in text or "OFFICIAL" in text:
        return "OFFICIAL"
    if "A_PLUS" in text or "A+" in text or (score is not None and score >= 90):
        return "A_PAPER"
    if "REVIEW" in text or (score is not None and score >= 75):
        return "REVIEW"
    if "WATCH" in text or (score is not None and score >= 45):
        return "WATCH"
    if "BLOCK" in text or "NO_BET" in text or "NO BET" in text:
        return "BLOCKED"
    return "NO_BET"

def add(board, game, away="", home=""):
    if not away or not home:
        away, home = parse_game(game)
    key = gkey(game, away, home)
    if not key: return None
    if key not in board:
        board[key] = {"game": game or f"{away} @ {home}", "awayTeam": away, "homeTeam": home, "opps": [], "contexts": {}, "sourceFilesUsed": []}
    return board[key]

def source(item, name):
    if name not in item["sourceFilesUsed"]: item["sourceFilesUsed"].append(name)

def add_public(board):
    name="ASTRODDS-public-board-categories-latest.json"
    data=load_json(ASTRO/name)
    for key,status in [("aPick","OFFICIAL"),("aPicks","OFFICIAL"),("valueLean","REVIEW"),("valueLeans","REVIEW"),("actionLean","WATCH"),("actionLeans","WATCH")]:
        rows=data.get(key,[])
        if not isinstance(rows,list): continue
        for r in rows:
            game=fv(r,["game","Game","matchup"])
            item=add(board,game)
            if not item: continue
            item["opps"].append({"pick":fv(r,["pick","Pick","team","selection"]),"marketType":"MONEYLINE","price":get_price(r),"modelProbability":fv(r,["modelProbability","modelProb","probability","Model"]),"edgePct":fv(r,["edgePct","edge","Edge"]),"baseballPredScore":"","grade":"A" if status=="OFFICIAL" else status,"status":status,"telegramEligible":status=="OFFICIAL","mainReason":f"Public board category: {key}","riskReason":"","source":name})
            source(item,name)

def add_ml_bbp(board):
    name="ASTRODDS-moneyline-baseballpred-sidecar-latest.json"
    data=load_json(ASTRO/name)
    rows=data.get("candidates",[]) if isinstance(data,dict) else []
    if not rows: rows=flatten(data)
    for r in rows:
        game=fv(r,["game","Game","matchup"])
        item=add(board,game)
        if not item: continue
        score=fnum(fv(r,["score","Score","baseballPredScore","moneylineBaseballPredScore"]),None)
        grade=fv(r,["moneylineBaseballPredGrade","grade","Grade","decision"])
        status=infer_status(grade, fv(r,["decision","Decision"]), score)
        if status=="OFFICIAL": status="A_PAPER"
        item["opps"].append({"pick":fv(r,["pick","Pick","team","selection"]),"marketType":"MONEYLINE","price":get_price(r),"modelProbability":fv(r,["modelProbability","probability","probProxy","ProbProxy"]),"edgePct":fv(r,["edgePct","edge","Edge"]),"baseballPredScore":"" if score is None else round(score,2),"grade":grade,"status":status,"telegramEligible":False,"mainReason":"BaseballPred Moneyline sidecar likes this pick.","riskReason":"Paper only until BaseballPred sidecar proves better than live 135.","source":name})
        source(item,name)

def add_ou_file(board, filename):
    data=load_json(ASTRO/filename)
    rows=flatten(data)
    for r in rows:
        pick=str(fv(r,["pick","Pick","selection"])).lower()
        if "over" not in pick and "under" not in pick: continue
        game=fv(r,["game","Game","matchup"])
        item=add(board,game)
        if not item: continue
        line=get_line(r)
        edge=fv(r,["edgeRuns","EdgeRuns","edge_runs"])
        score=fnum(fv(r,["score","Score","strictScore","StrictScore","battingScore","BattingScore"]),None)
        grade=fv(r,["grade","Grade","decision","battingAdjustedV2Grade","baseGrade"])
        status=infer_status(grade, fv(r,["decision","Decision"]), score)
        if status=="OFFICIAL": status="A_PAPER"
        half=is_half(line)
        tele=half and (("A_PLUS" in str(grade).upper()) or ("A+" in str(grade).upper())) and fnum(edge,0) >= 1.75
        risk="" if tele else ("Whole-number O/U line not Telegram eligible." if not half else "O/U is dashboard/paper only under current live 136 rules.")
        item["opps"].append({"pick":fv(r,["pick","Pick","selection"]),"marketType":"OU","line":line,"price":get_price(r),"projected":fv(r,["projected","Projected","projectedTotal"]),"edgeRuns":edge,"modelProbability":fv(r,["probProxy","ProbProxy","probability"]),"baseballPredScore":"" if score is None else round(score,2),"grade":grade,"status":status,"telegramEligible":tele,"mainReason":"O/U sidecar opportunity.","riskReason":risk,"source":filename})
        source(item,filename)

def merge_context(board, path, label):
    for r in read_csv(path):
        game=fv(r,["game","Game","matchup"])
        away=fv(r,["awayTeam","away_team","away"])
        home=fv(r,["homeTeam","home_team","home"])
        if not game and away and home: game=f"{away} @ {home}"
        item=add(board,game,away,home)
        if not item: continue
        compact={k:v for k,v in r.items() if str(v).strip()!=""}
        item["contexts"].setdefault(label,[]).append(dict(list(compact.items())[:35]))
        source(item,path.name)

def merge_bpen(board):
    rows=read_csv(ASTRO/"ASTRODDS-bpen-whip35-exact-statsapi-latest.csv")
    idx={tk(r.get("teamName")):r for r in rows}
    for item in board.values():
        vals=[]
        for side in ["awayTeam","homeTeam"]:
            r=idx.get(tk(item.get(side)))
            if r: vals.append({"team":r.get("teamName"),"Bpen_WHIP_35":r.get("Bpen_WHIP_35"),"games_in_window":r.get("games_in_window")})
        item["contexts"]["exactBpenWhip35"]=vals

def build_rows(board):
    rows=[]
    for item in board.values():
        opps=item["opps"] or [{"pick":"","marketType":"GAME","status":"NO_BET","telegramEligible":False,"mainReason":"No clean opportunity found.","riskReason":"Edge below threshold or missing price/context.","baseballPredScore":0}]
        for o in opps:
            score=fnum(o.get("baseballPredScore"),None)
            if score is None:
                ep=fnum(o.get("edgePct"),None); er=fnum(o.get("edgeRuns"),None)
                score=50+ep*3 if ep is not None else (50+er*20 if er is not None else 0)
            rows.append({"game":item["game"],"awayTeam":item.get("awayTeam",""),"homeTeam":item.get("homeTeam",""),"pick":o.get("pick",""),"marketType":o.get("marketType",""),"line":o.get("line",""),"price":o.get("price",""),"modelProbability":o.get("modelProbability",""),"edgePct":o.get("edgePct",""),"edgeRuns":o.get("edgeRuns",""),"baseballPredScore":round(score,2),"grade":o.get("grade",""),"status":o.get("status","NO_BET"),"telegramEligible":bool(o.get("telegramEligible",False)),"mainReason":o.get("mainReason",""),"riskReason":o.get("riskReason",""),"contexts":item.get("contexts",{}),"sourceFilesUsed":item.get("sourceFilesUsed",[])})
    rows.sort(key=lambda r:(status_rank(r["status"]),-fnum(r["baseballPredScore"],0)))
    for i,r in enumerate(rows,1): r["rank"]=i
    return rows

def main():
    REPORTS.mkdir(parents=True,exist_ok=True); ASTRO.mkdir(parents=True,exist_ok=True)
    board={}
    add_public(board)
    add_ml_bbp(board)
    for fn in ["ASTRODDS-over-under-expected-total-model-latest.json","ASTRODDS-ou-v2-strict-paper-score-latest.json","ASTRODDS-ou-v2-batting-context-score-latest.json","ASTRODDS-bbp-sidecars-with-exact-bpen-whip35-latest.json"]:
        add_ou_file(board,fn)
    for p,label in [(ASTRO/"VVS-pitcher-context-latest.csv","pitcher"),(ASTRO/"VVS-bullpen-context-latest.csv","bullpen"),(ASTRO/"ASTRODDS-free-injury-context-gate-latest.csv","injury"),(ASTRO/"ASTRODDS-full-slate-context-final-latest.csv","lineup")]:
        merge_context(board,p,label)
    for p in list(ASTRO.glob("*weather*latest.csv")):
        merge_context(board,p,"weather")
    merge_bpen(board)
    ranked=build_rows(board)
    counts={}
    for r in ranked: counts[r["status"]]=counts.get(r["status"],0)+1
    out={"generatedAt":datetime.now(timezone.utc).isoformat(),"games":len(board),"rows":len(ranked),"counts":counts,"telegramEligibleCount":sum(1 for r in ranked if r.get("telegramEligible")),"gameBoard":ranked,"rule":"Dashboard-sidecar only. Telegram live rules 135/136 unchanged."}
    OUT_JSON.write_text(json.dumps(out,indent=2),encoding="utf-8")
    lines=["ASTRODDS 198 BASEBALLPRED FULL SLATE RANKER","="*74,f"Generated UTC: {out['generatedAt']}","",f"Games found: {out['games']}",f"Ranked rows: {out['rows']}",f"Telegram eligible rows: {out['telegramEligibleCount']}","","Counts:"]
    for k,v in sorted(counts.items(),key=lambda kv:status_rank(kv[0])): lines.append(f"- {k}: {v}")
    lines+=["","Top ranked rows:"]
    for r in ranked[:30]: lines.append(f"- #{r['rank']} | {r['status']} | {r['marketType']} | {r['pick']} | {r['game']} | score={r['baseballPredScore']} | edge={r.get('edgePct') or r.get('edgeRuns')} | telegram={r['telegramEligible']} | {r['mainReason']}")
    lines+=["",f"JSON: {OUT_JSON}","","Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))
if __name__=="__main__": main()
