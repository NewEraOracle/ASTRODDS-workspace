
import argparse
from datetime import datetime, timedelta
from pathlib import Path
TEAM_MAP={"ARI":"Arizona Diamondbacks","ATL":"Atlanta Braves","BAL":"Baltimore Orioles","BOS":"Boston Red Sox","CHC":"Chicago Cubs","CHW":"Chicago White Sox","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers","HOU":"Houston Astros","KC":"Kansas City Royals","KCR":"Kansas City Royals","LAA":"Los Angeles Angels","LAD":"Los Angeles Dodgers","MIA":"Miami Marlins","MIL":"Milwaukee Brewers","MIN":"Minnesota Twins","NYM":"New York Mets","NYY":"New York Yankees","ATH":"Athletics","OAK":"Athletics","PHI":"Philadelphia Phillies","PIT":"Pittsburgh Pirates","SD":"San Diego Padres","SDP":"San Diego Padres","SEA":"Seattle Mariners","SF":"San Francisco Giants","SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TB":"Tampa Bay Rays","TBR":"Tampa Bay Rays","TEX":"Texas Rangers","TOR":"Toronto Blue Jays","WSH":"Washington Nationals","WAS":"Washington Nationals"}
HIT_EVENTS={"single":1,"double":2,"triple":3,"home_run":4}
WALK_EVENTS={"walk","intent_walk"}
HBP_EVENTS={"hit_by_pitch"}
K_EVENTS={"strikeout","strikeout_double_play"}
NON_AB_EVENTS=WALK_EVENTS|HBP_EVENTS|{"sac_fly","sac_bunt","catcher_interf"}
def team_name(abbr): return TEAM_MAP.get(str(abbr).upper(), str(abbr))
def batter_team(row):
    topbot=str(row.get("inning_topbot",""))
    if topbot.lower().startswith("top"): return team_name(row.get("away_team",""))
    if topbot.lower().startswith("bot"): return team_name(row.get("home_team",""))
    return ""
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days-back",type=int,default=60)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    import pandas as pd
    from pybaseball import statcast
    end=datetime.now().date()
    start=end-timedelta(days=args.days_back)
    df=statcast(start_dt=start.isoformat(), end_dt=end.isoformat())
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if df is None or len(df)==0:
        pd.DataFrame(columns=["Team","VsHand","wRCPlus","OPS","OBP","SLG","KPercent","BBPercent","Source","UpdatedAt"]).to_csv(args.out,index=False)
        print("NO_STATCAST_ROWS")
        return
    if "events" not in df.columns or "p_throws" not in df.columns:
        print("MISSING_EVENTS_OR_P_THROWS")
        raise SystemExit(2)
    df=df[df["events"].notna()].copy()
    df["Team"]=df.apply(batter_team,axis=1)
    df["VsHand"]=df["p_throws"].astype(str).str.upper().str[0]
    df=df[(df["Team"].astype(str).str.len()>0)&(df["VsHand"].isin(["L","R"]))]
    rows=[]
    for (team,hand),g in df.groupby(["Team","VsHand"]):
        pa=len(g); hits=tb=bb=hbp=k=ab=0
        for ev in g["events"].astype(str):
            if ev in HIT_EVENTS: hits+=1; tb+=HIT_EVENTS[ev]
            if ev in WALK_EVENTS: bb+=1
            if ev in HBP_EVENTS: hbp+=1
            if ev in K_EVENTS: k+=1
            if ev not in NON_AB_EVENTS: ab+=1
        obp_denom=ab+bb+hbp
        obp=(hits+bb+hbp)/obp_denom if obp_denom else 0
        slg=tb/ab if ab else 0
        ops=obp+slg
        rows.append({"Team":team,"VsHand":hand,"wRCPlus":"","OPS":round(ops,3),"OBP":round(obp,3),"SLG":round(slg,3),"KPercent":round((k/pa)*100,1) if pa else 0,"BBPercent":round((bb/pa)*100,1) if pa else 0,"Source":f"pybaseball Statcast derived from real events {start.isoformat()} to {end.isoformat()}","UpdatedAt":datetime.now().isoformat()})
    out=pd.DataFrame(rows).sort_values(["Team","VsHand"])
    out.to_csv(args.out,index=False)
    print(f"OK rows={len(out)} out={args.out}")
if __name__=="__main__": main()
