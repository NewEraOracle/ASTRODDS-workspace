import argparse,csv,json,sqlite3
from pathlib import Path
from datetime import datetime
def rows(p):
 try:
  with p.open('r',encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
 except Exception: return []
def num(x):
 try: return float(str(x).replace('%','').replace('¢','').replace(',','.'))
 except Exception: return None
def main():
 pa=argparse.ArgumentParser(); pa.add_argument('--root',required=True); a=pa.parse_args(); root=Path(a.root); astro=root/'.astrodds'; db=astro/'astrodds_prod_core.db'
 if not db.exists(): __import__('subprocess').call(['python',str(root/'mlb-engine/baseballpred-inspired/scripts/386_prod_core_db_init.py'),'--root',str(root)])
 con=sqlite3.connect(db); cur=con.cursor(); now=datetime.now().isoformat(); line=rows(astro/'ASTRODDS-289-best-price-line-shopping-latest.csv'); train=rows(astro/'ASTRODDS-model-training-dataset-latest.csv')
 for r in line: cur.execute('INSERT INTO line_shopping(game,pick,mlb_status,model_probability,best_entry,best_book,edge_vs_best,decision,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(r.get('Game',''),r.get('Pick',''),r.get('MlbStatus',''),num(r.get('ModelProbability')),num(r.get('BestEntry')),r.get('BestBook',''),num(r.get('EdgeVsBest')),r.get('LineShopDecision',''),now))
 for r in train: cur.execute('INSERT INTO settlement_ledger(game,pick,result,winner,roi,settled_at) VALUES(?,?,?,?,?,?)',(r.get('Game',''),r.get('Pick',''),r.get('Result') or r.get('label',''),r.get('Winner',''),num(r.get('ROI')),now))
 con.commit(); con.close(); out={'generatedAt':now,'status':'OK','lineRows':len(line),'trainingRows':len(train)}; (astro/'ASTRODDS-387-import-latest-artifacts-to-db-latest.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); lines=['ASTRODDS 387 IMPORT LATEST ARTIFACTS TO DB','','Status: OK',f'- line shopping rows: {len(line)}',f'- training rows: {len(train)}']; (astro/'ASTRODDS-387-import-latest-artifacts-to-db-latest.txt').write_text('\n'.join(lines),encoding='utf-8'); print('\n'.join(lines))
if __name__=='__main__': main()
