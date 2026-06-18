from pathlib import Path
from datetime import datetime, timezone
import json
ROOT=Path(__file__).resolve().parents[3]
ASTRO=ROOT/".astrodds"; REPORTS=ROOT/"mlb-engine"/"baseballpred-inspired"/"reports"
IN_JSON=ASTRO/"ASTRODDS-baseballpred-full-slate-ranker-latest.json"; OUT_JSON=ASTRO/"ASTRODDS-full-slate-game-board-latest.json"; REPORT=REPORTS/"200_astrodds_full_slate_game_board_report.txt"
def load(p):
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}
def section(title,rows):
    lines=["",title,"-"*len(title)]
    if not rows: return lines+["- none"]
    for r in rows:
        edge=r.get("edgePct") or r.get("edgeRuns") or ""; lp=r.get("line") or r.get("price") or ""
        lines.append(f"#{r.get('rank')} | {r.get('status')} | {r.get('marketType')} | {r.get('pick')} | {r.get('game')} | line/price={lp} | score={r.get('baseballPredScore')} | edge={edge} | telegram={r.get('telegramEligible')} | {r.get('mainReason')}")
        if r.get("riskReason"): lines.append(f"   Risk: {r.get('riskReason')}")
    return lines
def main():
    REPORTS.mkdir(parents=True,exist_ok=True); ASTRO.mkdir(parents=True,exist_ok=True)
    data=load(IN_JSON); rows=data.get("gameBoard",[]) if isinstance(data,dict) else []
    counts={}
    for r in rows: counts[r.get("status","NO_BET")]=counts.get(r.get("status","NO_BET"),0)+1
    summary={"totalRows":len(rows),"totalGames":data.get("games",0),"official":counts.get("OFFICIAL",0),"aPaper":counts.get("A_PAPER",0),"review":counts.get("REVIEW",0),"watch":counts.get("WATCH",0),"blockedNoBet":counts.get("BLOCKED",0)+counts.get("NO_BET",0),"moneyline":sum(1 for r in rows if r.get("marketType")=="MONEYLINE"),"ou":sum(1 for r in rows if r.get("marketType")=="OU"),"telegramEligible":sum(1 for r in rows if r.get("telegramEligible"))}
    out={"generatedAt":datetime.now(timezone.utc).isoformat(),"summary":summary,"gameBoard":rows,"rule":"Dashboard only. Telegram remains strict 135/136."}
    OUT_JSON.write_text(json.dumps(out,indent=2),encoding="utf-8")
    lines=["ASTRODDS 200 FULL SLATE GAME BOARD","="*64,f"Generated UTC: {out['generatedAt']}","","Top summary:"]
    for k,v in summary.items(): lines.append(f"- {k}: {v}")
    lines+=section("OFFICIAL PICKS",[r for r in rows if r.get("status")=="OFFICIAL"])
    lines+=section("A_PAPER / BASEBALLPRED PAPER",[r for r in rows if r.get("status")=="A_PAPER"])
    lines+=section("REVIEW BOARD",[r for r in rows if r.get("status")=="REVIEW"])
    lines+=section("WATCHLIST",[r for r in rows if r.get("status")=="WATCH"])
    lines+=section("BLOCKED / NO BET",[r for r in rows if r.get("status") in ("BLOCKED","NO_BET")])
    lines+=["",f"JSON: {OUT_JSON}","Rule: Dashboard only. No Telegram send."]
    REPORT.write_text("\n".join(lines),encoding="utf-8"); print("\n".join(lines))
if __name__=="__main__": main()
