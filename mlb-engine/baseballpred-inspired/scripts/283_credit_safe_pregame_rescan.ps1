$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) } catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        try {
            $p = $row.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return ""
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }

    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
}


$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

Ensure-Dir $astro
Load-EnvLocal $root

$outTxt = Join-Path $astro "ASTRODDS-283-credit-safe-pregame-rescan-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-283-credit-safe-pregame-rescan-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-283-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 283F CREDIT-SAFE PREGAME RESCAN FIXED" -ForegroundColor Cyan
Write-Host "Free sources first. Paid odds only through 281. Production router uses existing market file." -ForegroundColor Cyan
Write-Host ""

$steps = @()
$childLog = @()

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{ Name=$name; Status="MISSING"; ExitCode=""; DurationSec=0 }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{ Name=$name; Status="OK"; ExitCode="0"; DurationSec=$duration }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="$exitCode"; DurationSec=$duration }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"
        return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="1"; DurationSec=$duration }
    }
}

# FREE refresh only. These should not burn Odds API credits.
$steps += ,(Run-Step "259 MLB live sources" (Join-Path $scripts "259_fetch_mlb_live_sources.ps1"))
$steps += ,(Run-Step "274 rolling bullpen 3d/7d" (Join-Path $scripts "274_build_rolling_bullpen_3d_7d.ps1"))
$steps += ,(Run-Step "275 injury roster status" (Join-Path $scripts "275_fetch_full_roster_injury_status.ps1"))
$steps += ,(Run-Step "260 weather" (Join-Path $scripts "260_fetch_weather_ballpark_sources.ps1"))
$steps += ,(Run-Step "278 source board quality" (Join-Path $scripts "278_rebuild_source_board_with_quality_sources.ps1"))
$steps += ,(Run-Step "265 baseline model coverage" (Join-Path $scripts "265_build_source_first_baseline_model.ps1"))
$steps += ,(Run-Step "282 potential candidate board" (Join-Path $scripts "282_build_potential_candidate_board.ps1"))

$candidates = Safe-Csv (Join-Path $astro "ASTRODDS-potential-candidate-board-latest.csv")
$oddsCandidates = @($candidates | Where-Object { (Get-Val $_ @("CandidateLevel")) -eq "ODDS_RESCAN_CANDIDATE" })

$oddsDecision = ""
if ($oddsCandidates.Count -gt 0) {
    $oddsDecision = "candidate board has $($oddsCandidates.Count) ODDS_RESCAN_CANDIDATE rows; run 281 credit-aware odds fetch"
    $steps += ,(Run-Step "281 credit-aware market fetch" (Join-Path $scripts "281_credit_aware_market_fetch.ps1"))
} else {
    $oddsDecision = "no ODDS_RESCAN_CANDIDATE rows; paid odds skipped"
    Write-Host "Skipping paid odds call: $oddsDecision" -ForegroundColor Yellow
}

# IMPORTANT:
# Do NOT run 279 here, because 279 calls 273 directly and can spend Odds API credits.
# Run 271 production router instead. It uses the current market file already created by 281 or previous safe calls.
$steps += ,(Run-Step "271 production final router" (Join-Path $scripts "271_production_final_router.ps1"))
$steps += ,(Run-Step "286 advanced gap audit" (Join-Path $scripts "286_baseballpred_advanced_gap_audit.ps1"))
$steps += ,(Run-Step "287 final automation status" (Join-Path $scripts "287_final_automation_status.ps1"))

$childLog | Set-Content -Encoding UTF8 $outChildLog

$productionTelegram = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"
$telegram = ""
if (Test-Path $productionTelegram) { $telegram = Get-Content $productionTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 283F CREDIT-SAFE PREGAME RESCAN FIXED"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Odds decision: $oddsDecision"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "FINAL MESSAGE"
$lines += $telegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    oddsDecision = $oddsDecision
    steps = @($steps)
    productionTelegram = $productionTelegram
    childLog = $outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
