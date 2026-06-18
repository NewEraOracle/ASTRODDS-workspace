import argparse,json
from pathlib import Path
from datetime import datetime
def txt(p):
 try: return p.read_text(encoding='utf-8')
 except Exception: return ''
def main():
 pa=argparse.ArgumentParser(); pa.add_argument('--root',required=True); a=pa.parse_args(); astro=Path(a.root)/'.astrodds'; checks=[]
 def add(n,s): checks.append({'name':n,'status':s})
 add('server_autopilot','OK' if (astro/'ASTRODDS-343-one-command-heartbeat-latest.txt').exists() else 'MISSING')
 add('planner','OK' if (astro/'ASTRODDS-337-smart-scan-window-planner-latest.txt').exists() else 'MISSING')
 add('telegram_guard','OK' if 'Status: SAFE' in txt(astro/'ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt') else 'CHECK')
 prem=txt(astro/'ASTRODDS-362-premium-readiness-report-latest.txt')
 add('bullpen_real','OK' if 'Real bullpen pitch usage teams: 28' in prem else 'CHECK')
 add('platoon_real','OK' if 'Platoon fully connected rows: 0' not in prem else 'PARTIAL_OR_MISSING')
 add('xfip_real','OPTIONAL_MISSING' if 'True xFIP fully connected rows: 0' in prem else 'OK')
 add('leverage_real','OPTIONAL_MISSING' if 'True leverage connected teams: 0' in prem else 'OK')
 status='OK' if all(c['status'] not in ['MISSING','CHECK'] for c in checks if c['name'] not in ['xfip_real','leverage_real']) else 'CHECK'
 lines=['ASTRODDS 391 SOURCE HEALTH MONITOR','',f'Status: {status}','']+[f"- {c['status']} | {c['name']}" for c in checks]+['','NOTE','- xFIP/leverage are optional premium sources if blocked/paid; do not fake them.']
 (astro/'ASTRODDS-391-source-health-monitor-latest.txt').write_text('\n'.join(lines),encoding='utf-8'); (astro/'ASTRODDS-391-source-health-monitor-latest.json').write_text(json.dumps({'generatedAt':datetime.now().isoformat(),'status':status,'checks':checks},indent=2),encoding='utf-8'); print('\n'.join(lines))
if __name__=='__main__': main()
