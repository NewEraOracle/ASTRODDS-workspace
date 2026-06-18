
import argparse, sys
from datetime import datetime
from pathlib import Path
TEAM_MAP={"ARI":"Arizona Diamondbacks","ATL":"Atlanta Braves","BAL":"Baltimore Orioles","BOS":"Boston Red Sox","CHC":"Chicago Cubs","CHW":"Chicago White Sox","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers","HOU":"Houston Astros","KC":"Kansas City Royals","KCR":"Kansas City Royals","LAA":"Los Angeles Angels","LAD":"Los Angeles Dodgers","MIA":"Miami Marlins","MIL":"Milwaukee Brewers","MIN":"Minnesota Twins","NYM":"New York Mets","NYY":"New York Yankees","ATH":"Athletics","OAK":"Athletics","PHI":"Philadelphia Phillies","PIT":"Pittsburgh Pirates","SD":"San Diego Padres","SDP":"San Diego Padres","SEA":"Seattle Mariners","SF":"San Francisco Giants","SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TB":"Tampa Bay Rays","TBR":"Tampa Bay Rays","TEX":"Texas Rangers","TOR":"Toronto Blue Jays","WSH":"Washington Nationals","WAS":"Washington Nationals"}
def team_name(t): return TEAM_MAP.get(str(t or "").strip().upper(), str(t or "").strip())
def find_col(cols, candidates):
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
    ap.add_argument("--year", type=int, default=datetime.now().year)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    import pandas as pd
    from pybaseball import pitching_stats
    try:
        df=pitching_stats(args.year,args.year,qual=0)
    except TypeError:
        df=pitching_stats(args.year,args.year)
    cols=list(df.columns)
    name_col=find_col(cols,["Name","PlayerName","Player"])
    team_col=find_col(cols,["Team","team"])
    throws_col=find_col(cols,["Throws","Hand","P_Throws"])
    fip_col=find_col(cols,["FIP"])
    xfip_col=find_col(cols,["xFIP","XFIP"])
    kbb_col=find_col(cols,["K-BB%","KBB%","KBBPercent","K-BB"])
    siera_col=find_col(cols,["SIERA"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if not name_col or not team_col or not xfip_col:
        pd.DataFrame(columns=["Pitcher","Team","Throws","FIP","xFIP","KBBPercent","SIERA","Source","UpdatedAt"]).to_csv(args.out,index=False)
        print(f"MISSING_REQUIRED_COLUMNS name={name_col} team={team_col} xFIP={xfip_col}")
        print("Available columns:", cols[:100])
        sys.exit(2)
    out=pd.DataFrame()
    out["Pitcher"]=df[name_col].astype(str)
    out["Team"]=df[team_col].apply(team_name)
    out["Throws"]=df[throws_col].astype(str) if throws_col else ""
    out["FIP"]=df[fip_col] if fip_col else ""
    out["xFIP"]=df[xfip_col]
    out["KBBPercent"]=df[kbb_col] if kbb_col else ""
    out["SIERA"]=df[siera_col] if siera_col else ""
    out["Source"]=f"pybaseball pitching_stats FanGraphs season {args.year}"
    out["UpdatedAt"]=datetime.now().isoformat()
    out=out.dropna(subset=["Pitcher","Team","xFIP"])
    out=out[(out["Pitcher"].astype(str).str.strip()!="") & (out["xFIP"].astype(str).str.strip()!="")]
    out.to_csv(args.out,index=False)
    print(f"OK rows={len(out)} out={args.out}")
if __name__=="__main__": main()
