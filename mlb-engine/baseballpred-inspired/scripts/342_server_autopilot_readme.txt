ASTRODDS SERVER + SMART AUTOPILOT PATCH 336-342

Purpose:
Recreate the old workflow where you start the server, but now with the new smart scan logic.

Adds:
336 start server legacy mode
337 smart scan window planner
338 one smart server+scan cycle
339 keepalive loop every X minutes
340 Windows scheduled task every 10 minutes
341 open status reports
342 this readme

Scan logic:
- > 4h before game: morning/watchlist free-only
- 240 to 75 min: free context only
- 75 to 45 min: pregame context scan
- 45 to 15 min: final value scan, paid odds only candidate-safe
- < 15 min: last-call strict scan
- after start: block new drops, settlement/watch only
- final: settlement only

Install:
powershell -ExecutionPolicy Bypass -File ".\INSTALL_ASTRODDS_SERVER_SMART_AUTOPILOT_PATCH.ps1"

One cycle:
cd "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\338_autopilot_server_scan_cycle.ps1"

Leave running:
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\339_keepalive_server_autopilot_loop.ps1" -IntervalMinutes 10

Install task:
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\340_install_server_autopilot_task.ps1"

Open status:
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\341_show_autopilot_status.ps1"
