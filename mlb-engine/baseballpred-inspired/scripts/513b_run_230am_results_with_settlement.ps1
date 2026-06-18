param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

powershell -ExecutionPolicy Bypass -File "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\mlb-engine\baseballpred-inspired\scripts\512_auto_settle_client_leans_loop.ps1" -Workspace "$Workspace"
powershell -ExecutionPolicy Bypass -File "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\mlb-engine\baseballpred-inspired\scripts\513_send_230am_client_lean_results_telegram.ps1" -Workspace "$Workspace"
