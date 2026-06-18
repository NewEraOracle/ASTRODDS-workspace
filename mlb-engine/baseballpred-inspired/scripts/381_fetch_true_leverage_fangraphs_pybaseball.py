
import argparse, sys
from datetime import datetime
from pathlib import Path
TEAM_MAP={"ARI":"Arizona Diamondbacks","ATL":"Atlanta Braves","BAL":"Baltimore Orioles","BOS":"Boston Red Sox","CHC":"Chicago Cubs","CHW":"Chicago White Sox","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers","HOU":"Houston Astros","KC":"Kansas City Royals","KCR":"Kansas City Royals","LAA":"Los Angeles Angels","LAD":"Los Angeles Dodgers","MIA":"Miami Marlins","MIL":"Milwaukee Brewers","MIN":"Minnesota Twins","NYM":"New York Mets","NYY":"New York Yankees","ATH":"Athletics","OAK":"Athletics","PHI":"Philadelphia Phillies","PIT":"Pittsburgh Pirates","SD":"San Diego Padres","SDP":"San Diego Padres","SEA":"Seattle Mariners","SF":"San Francisco Giants","SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TB":"Tampa Bay Rays","TBR":"Tampa Bay Rays","TEX":"Texas Rangers","TOR":"Toronto Blue Jays","WSH":"Washington Nationals","WAS":"Washington Nationals"}
def team_name(t): return TEAM_MAP.get(str(t or "").strip().upper(), str(t or "").strip())
def find_col(cols,candidates):
    lower={c.lower():c for c in cols}
    for cand in candidates:
        if cand.lower() in lower: return lower[cand.lower()]
    norm={c.lower().replace("-","").replace("%","").replace(" ",""):c for c in cols}
    for cand in candidates:
        key=cand.lower().replace("-","").replace("%","").replace(" ","")
        if key in norm: return norm[key]
    return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,default=datetime.now().year)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    import pandas as pd
    from pybaseball import pitching_stats
    try: df=pitching_stats(args.year,args.year,qual=0)
    except TypeError: df=pitching_stats(args.year,args.year)
    cols=list(df.columns)
    name_col=find_col(cols,["Name","PlayerName","Player"])
    team_col=find_col(cols,["Team","team"])
    g_col=find_col(cols,["G"])
    gs_col=find_col(cols,["GS"])
    li_col=find_col(cols,["gmLI","inLI","exLI"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if not name_col or not team_col or not li_col:
        pd.DataFrame(columns=["Team","Reliever","Role","LeverageIndex","AvailabilityStatus","Source","UpdatedAt"]).to_csv(args.out,index=False)
        print(f"MISSING_REQUIRED_COLUMNS name={name_col} team={team_col} li={li_col}")
        print("Available columns:", cols[:140])
        sys.exit(2)
    rows=[]
    for _,r in df.iterrows():
        name=str(r.get(name_col,"")).strip(); team=team_name(r.get(team_col,"")); li=r.get(li_col,"")
        if not name or not team or str(li).strip()=="" or str(li).lower()=="nan": continue
        g=r.get(g_col,0) if g_col else 0; gs=r.get(gs_col,0) if gs_col else 0
        try: role="Reliever" if float(g)>float(gs) else "Starter/Mixed"
        except Exception: role="Pitcher"
        rows.append({"Team":team,"Reliever":name,"Role":role,"LeverageIndex":round(float(li),3),"AvailabilityStatus":"REAL_FANGRAPHS_LEVERAGE_SEASON_CONTEXT","Source":f"pybaseball pitching_stats FanGraphs {li_col} season {args.year}","UpdatedAt":datetime.now().isoformat()})
    out=pd.DataFrame(rows)
    out.to_csv(args.out,index=False)
    print(f"OK rows={len(out)} li_col={li_col} out={args.out}")
if __name__=="__main__": main()
