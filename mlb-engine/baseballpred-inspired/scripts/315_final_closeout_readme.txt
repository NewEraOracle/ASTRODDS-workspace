ASTRODDS FINAL PRODUCTION CLOSEOUT 307-315

This is the final closeout pack.

307 Env/config doctor
308 Final production one-command
309 Client + admin reports
310 Odds credit budget dashboard
311 Windows Task Scheduler installer
312 Final readiness gate
313 Safe start server + one production scan
314 Show final commands
315 This readme

Install:
powershell -ExecutionPolicy Bypass -File ".\INSTALL_ASTRODDS_FINAL_PRODUCTION_CLOSEOUT_PATCH.ps1"

Final one command:
cd "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\308_final_production_one_command.ps1"

Important:
- Keep Telegram dry-run until you trust live results:
  $env:ASTRODDS_TELEGRAM_SEND="NO"

- Enable Telegram only later:
  $env:ASTRODDS_TELEGRAM_SEND="YES"
  $env:ASTRODDS_TELEGRAM_BOT_TOKEN="..."
  $env:ASTRODDS_TELEGRAM_CHAT_ID="..."

- This bot must be marketed as data-driven value alerts, not guaranteed wins.
