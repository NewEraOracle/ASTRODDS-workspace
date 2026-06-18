$ErrorActionPreference = "Continue"
param(
    [ValidateSet("DRYRUN","SEND")]
    [string]$Mode = "DRYRUN"
)

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
if (!(Test-Path $astro)) { New-Item -ItemType Directory -Force -Path $astro | Out-Null }

$outTxt = Join-Path $astro "ASTRODDS-334-telegram-send-mode-toggle-latest.txt"

if ($Mode -eq "SEND") {
    [Environment]::SetEnvironmentVariable("ASTRODDS_TELEGRAM_SEND", "YES", "User")
    $env:ASTRODDS_TELEGRAM_SEND = "YES"
    $status = "REAL_SEND_ENABLED_FOR_USER_ENV"
} else {
    [Environment]::SetEnvironmentVariable("ASTRODDS_TELEGRAM_SEND", "NO", "User")
    $env:ASTRODDS_TELEGRAM_SEND = "NO"
    $status = "DRY_RUN_ENABLED_FOR_USER_ENV"
}

$lines = @()
$lines += "ASTRODDS 334 TELEGRAM SEND MODE TOGGLE"
$lines += ""
$lines += "Mode requested: $Mode"
$lines += "Status: $status"
$lines += ""
$lines += "Current process ASTRODDS_TELEGRAM_SEND=$env:ASTRODDS_TELEGRAM_SEND"
$lines += ""
$lines += "Recommendation: keep DRYRUN until you trust at least 1-2 live slates."
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
