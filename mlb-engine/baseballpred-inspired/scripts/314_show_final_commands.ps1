$ErrorActionPreference = "Continue"
$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"

Write-Host ""
Write-Host "ASTRODDS FINAL COMMANDS" -ForegroundColor Cyan
Write-Host ""

Write-Host "1) Final production scan:"
Write-Host 'cd "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"'
Write-Host 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\308_final_production_one_command.ps1"'
Write-Host ""

Write-Host "2) Start server + one production scan:"
Write-Host 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\313_safe_start_server_autoscan.ps1"'
Write-Host ""

Write-Host "3) Install scheduled scan every 30 minutes:"
Write-Host 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\311_install_windows_task_scheduler.ps1"'
Write-Host ""

Write-Host "4) Open client report:"
Write-Host 'notepad ".\.astrodds\ASTRODDS-FINAL-client-summary-latest.txt"'
Write-Host ""

Write-Host "5) Open admin report:"
Write-Host 'notepad ".\.astrodds\ASTRODDS-FINAL-admin-report-latest.txt"'
Write-Host ""

Write-Host "6) Keep Telegram dry-run:"
Write-Host '$env:ASTRODDS_TELEGRAM_SEND="NO"'
Write-Host ""

Write-Host "7) Enable Telegram real send later:"
Write-Host '$env:ASTRODDS_TELEGRAM_SEND="YES"'
Write-Host '$env:ASTRODDS_TELEGRAM_BOT_TOKEN="YOUR_TOKEN"'
Write-Host '$env:ASTRODDS_TELEGRAM_CHAT_ID="YOUR_CHAT_ID"'
Write-Host ""
exit 0
