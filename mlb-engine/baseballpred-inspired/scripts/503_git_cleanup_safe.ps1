param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

Write-Host "ASTRODDS 503 SAFE GIT CLEANUP"
Write-Host "This removes generated reports only. It does not delete source scripts."

Remove-Item ".\mlb-engine\baseballpred-inspired\reports\*_report.txt" -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Trackable changes:"
git status --short | Select-String -Pattern "^\s*M|^\s*A|^\s*D"

Write-Host ""
Write-Host "Untracked scripts warning:"
git status --short | Select-String -Pattern "^\?\? mlb-engine/baseballpred-inspired/scripts/" | Select-Object -First 40

Write-Host ""
Write-Host "Rule: do not use git add ."
