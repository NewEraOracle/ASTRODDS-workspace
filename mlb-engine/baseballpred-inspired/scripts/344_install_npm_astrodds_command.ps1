$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$pkgPath = Join-Path $root "package.json"
$outTxt = Join-Path $root ".astrodds\ASTRODDS-344-install-npm-command-latest.txt"

if (!(Test-Path (Join-Path $root ".astrodds"))) { New-Item -ItemType Directory -Force -Path (Join-Path $root ".astrodds") | Out-Null }

Write-Host ""
Write-Host "ASTRODDS 344 INSTALL NPM COMMAND" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $pkgPath)) {
    Write-Host "No package.json at workspace root. Creating minimal package.json with ASTRODDS scripts." -ForegroundColor Yellow
    $obj = [ordered]@{
        scripts = [ordered]@{}
    }
} else {
    $raw = Get-Content $pkgPath -Raw
    try { $obj = $raw | ConvertFrom-Json -AsHashtable }
    catch {
        Write-Host "package.json parse failed. Backup and recreate safe scripts-only package.json." -ForegroundColor Yellow
        Copy-Item $pkgPath "$pkgPath.backup-before-astrodds-$(Get-Date -Format 'yyyyMMdd-HHmmss')" -Force
        $obj = [ordered]@{ scripts = [ordered]@{} }
    }
}

if (-not $obj.ContainsKey("scripts") -or $null -eq $obj.scripts) {
    $obj["scripts"] = [ordered]@{}
}

$obj.scripts["astrodds"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\343_one_command_local_server_autopilot.ps1"
$obj.scripts["astrodds:scan"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\338_autopilot_server_scan_cycle.ps1"
$obj.scripts["astrodds:status"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\346_one_command_status.ps1"
$obj.scripts["astrodds:stop"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\345_stop_local_autopilot.ps1"
$obj.scripts["astrodds:reports"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\341_show_autopilot_status.ps1"
$obj.scripts["astrodds:send"] = "powershell -ExecutionPolicy Bypass -File .\\mlb-engine\\baseballpred-inspired\\scripts\\343_one_command_local_server_autopilot.ps1 -SendTelegram"

$json = $obj | ConvertTo-Json -Depth 20
Set-Content -Encoding UTF8 $pkgPath $json

$lines = @()
$lines += "ASTRODDS 344 INSTALL NPM COMMAND"
$lines += ""
$lines += "Updated: $pkgPath"
$lines += ""
$lines += "Commands installed:"
$lines += "- npm run astrodds"
$lines += "- npm run astrodds:scan"
$lines += "- npm run astrodds:status"
$lines += "- npm run astrodds:stop"
$lines += "- npm run astrodds:reports"
$lines += "- npm run astrodds:send"
$lines += ""
$lines += "Recommended tonight:"
$lines += "npm run astrodds"
$lines += ""
$lines += "Telegram stays dry-run in npm run astrodds."
$lines += "Use npm run astrodds:send only when you intentionally want real sends."

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
