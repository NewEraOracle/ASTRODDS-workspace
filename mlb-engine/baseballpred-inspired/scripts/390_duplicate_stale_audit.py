import argparse,csv,json,collections
from pathlib import Path
from datetime import datetime
def read(p):
 try:
  with p.open('r',encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
 except Exception: return []
def main():
 pa=argparse.ArgumentParser(); pa.add_argument('--root',required=True); a=pa.parse_args(); astro=Path(a.root)/'.astrodds'; rows=read(astro/'ASTRODDS-289-best-price-line-shopping-latest.csv')
 d=collections.defaultdict(set); internal=0; stale=0
 for r in rows:
  d[(r.get('Game',''),r.get('Pick',''))].add(r.get('MlbStatus',''))
  if str(r.get('BestBook','')).lower()=='internal': internal+=1
  if r.get('MlbStatus') in ['Final','Game Over','In Progress'] and 'SEND' in str(r.get('LineShopDecision','')).upper(): stale+=1
 dup={f'{k[0]} | {k[1]}':list(v) for k,v in d.items() if len(v)>1}; status='FAIL' if stale else 'PASS'
 lines=['ASTRODDS 390 DUPLICATE / STALE AUDIT','',f'Status: {status}','',f'- line rows: {len(rows)}',f'- internal rows present: {internal}',f'- duplicate game/pick status groups: {len(dup)}',f'- stale SEND-like rows: {stale}']
 if dup: lines+=['','DUPLICATES']+[f'- {k} => {",".join(v)}' for k,v in list(dup.items())[:20]]
 (astro/'ASTRODDS-390-duplicate-stale-audit-latest.txt').write_text('\n'.join(lines),encoding='utf-8'); (astro/'ASTRODDS-390-duplicate-stale-audit-latest.json').write_text(json.dumps({'generatedAt':datetime.now().isoformat(),'status':status,'internalRows':internal,'duplicates':dup,'staleSendRows':stale},indent=2),encoding='utf-8'); print('\n'.join(lines)); raise SystemExit(0 if not stale else 1)
if __name__=='__main__': main()
