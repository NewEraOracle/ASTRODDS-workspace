import argparse,json,csv
from pathlib import Path
from datetime import datetime
def t(name,ok,detail=''): return {'test':name,'status':'PASS' if ok else 'FAIL','detail':detail}
def txt(p):
 try: return p.read_text(encoding='utf-8')
 except Exception: return ''
def main():
 pa=argparse.ArgumentParser(); pa.add_argument('--root',required=True); a=pa.parse_args(); root=Path(a.root); astro=root/'.astrodds'; tests=[]
 try: json.loads((root/'package.json').read_text(encoding='utf-8-sig')); tests.append(t('package_json_valid',True))
 except Exception as e: tests.append(t('package_json_valid',False,str(e)))
 tests.append(t('db_exists',(astro/'astrodds_prod_core.db').exists()))
 tests.append(t('telegram_guard_safe','Status: SAFE' in txt(astro/'ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt')))
 tests.append(t('230am_report_only','Moneyline230AM: FALSE_REPORT_ONLY' in txt(astro/'ASTRODDS-338-heartbeat-latest.txt') or '2:30 AM' in txt(astro/'ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt')))
 bad=False
 try:
  with (astro/'ASTRODDS-289-best-price-line-shopping-latest.csv').open('r',encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    if str(r.get('BestBook','')).lower()=='internal' and 'SEND' in str(r.get('LineShopDecision','')).upper(): bad=True
 except Exception: pass
 tests.append(t('no_internal_send_ok',not bad))
 status='PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL'; lines=['ASTRODDS 392 REGRESSION TEST SUITE','',f'Status: {status}','']+[f"- {x['status']} | {x['test']} | {x['detail']}" for x in tests]
 (astro/'ASTRODDS-392-regression-test-suite-latest.txt').write_text('\n'.join(lines),encoding='utf-8'); (astro/'ASTRODDS-392-regression-test-suite-latest.json').write_text(json.dumps({'generatedAt':datetime.now().isoformat(),'status':status,'tests':tests},indent=2),encoding='utf-8'); print('\n'.join(lines)); raise SystemExit(0 if status=='PASS' else 1)
if __name__=='__main__': main()
