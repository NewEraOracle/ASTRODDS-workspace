import argparse,sqlite3,json
from pathlib import Path
from datetime import datetime
schema=["CREATE TABLE IF NOT EXISTS scan_runs(id INTEGER PRIMARY KEY, run_id TEXT UNIQUE, started_at TEXT, status TEXT, global_action TEXT)","CREATE TABLE IF NOT EXISTS line_shopping(id INTEGER PRIMARY KEY, game TEXT, pick TEXT, mlb_status TEXT, model_probability REAL, best_entry REAL, best_book TEXT, edge_vs_best REAL, decision TEXT, updated_at TEXT)","CREATE TABLE IF NOT EXISTS settlement_ledger(id INTEGER PRIMARY KEY, game TEXT, pick TEXT, result TEXT, winner TEXT, roi REAL, settled_at TEXT)","CREATE TABLE IF NOT EXISTS source_status(source_name TEXT PRIMARY KEY, status TEXT, rows_count INTEGER, detail TEXT, updated_at TEXT)","CREATE TABLE IF NOT EXISTS audits(id INTEGER PRIMARY KEY, audit_name TEXT, status TEXT, detail TEXT, created_at TEXT)","CREATE TABLE IF NOT EXISTS regression_tests(id INTEGER PRIMARY KEY, test_name TEXT, status TEXT, detail TEXT, created_at TEXT)"]
def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',required=True); a=p.parse_args(); root=Path(a.root); astro=root/'.astrodds'; astro.mkdir(exist_ok=True); db=astro/'astrodds_prod_core.db'; con=sqlite3.connect(db); cur=con.cursor()
 for s in schema: cur.execute(s)
 con.commit(); counts={}
 for t in ['scan_runs','line_shopping','settlement_ledger','source_status','audits','regression_tests']:
  cur.execute(f'SELECT COUNT(*) FROM {t}'); counts[t]=cur.fetchone()[0]
 con.close(); out={'generatedAt':datetime.now().isoformat(),'status':'OK','db':str(db),'counts':counts}; (astro/'ASTRODDS-386-prod-core-db-init-latest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 lines=['ASTRODDS 386 PRODUCTION CORE DB INIT','','Status: OK',f'DB: {db}','']+[f'- {k}: {v}' for k,v in counts.items()]; (astro/'ASTRODDS-386-prod-core-db-init-latest.txt').write_text('\n'.join(lines),encoding='utf-8'); print('\n'.join(lines))
if __name__=='__main__': main()
