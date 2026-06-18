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

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) { return $n }
    return $null
}

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    $awayTeamName = ""
    $homeTeamName = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

function Avg($arr) {
    $vals = @()
    foreach ($x in @($arr)) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
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

$outTxt = Join-Path $astro "ASTRODDS-296-BASEBALLPRED-PLUS-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-296-BASEBALLPRED-PLUS-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-296-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 296 BASEBALLPRED++ RUNNER" -ForegroundColor Cyan
Write-Host "Runs credit-safe scan + BaseballPred++ upgrades." -ForegroundColor Cyan
Write-Host ""

$childLog = @()
function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan
    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }
    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })
        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$duration}
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exitCode";DurationSec=$duration}
        }
    } catch {
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$run = @(
    @{Name="283 credit-safe pregame rescan"; Path=Join-Path $scripts "283_credit_safe_pregame_rescan.ps1"},
    @{Name="289 best price line shopping"; Path=Join-Path $scripts "289_best_price_line_shopping_board.ps1"},
    @{Name="290 CLV snapshot"; Path=Join-Path $scripts "290_closing_line_snapshot.ps1"},
    @{Name="291 enhanced settlement"; Path=Join-Path $scripts "291_enhanced_settlement_roi_clv.ps1"},
    @{Name="292 confidence calibration apply"; Path=Join-Path $scripts "292_apply_confidence_calibration.ps1"},
    @{Name="293 ballpark advanced factors"; Path=Join-Path $scripts "293_ballpark_advanced_factors.ps1"},
    @{Name="294 travel rest timezone"; Path=Join-Path $scripts "294_travel_rest_timezone_context.ps1"},
    @{Name="295 BaseballPred++ context merge"; Path=Join-Path $scripts "295_baseballpred_plus_context_merge.ps1"},
    @{Name="297 Telegram auto-send safe"; Path=Join-Path $scripts "297_telegram_auto_send_safe.ps1"},
    @{Name="298 BaseballPred++ report"; Path=Join-Path $scripts "298_baseballpred_plus_report.ps1"}
)

$steps = @()
foreach ($s in $run) { $steps += ,(Run-Step $s.Name $s.Path) }
$childLog | Set-Content -Encoding UTF8 $outChildLog

$prodMsg = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"
$message = ""
if (Test-Path $prodMsg) { $message = Get-Content $prodMsg -Raw }

$lines = @()
$lines += "ASTRODDS 296 BASEBALLPRED++ RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "FINAL PRODUCTION MESSAGE"
$lines += $message

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    productionMessage=$prodMsg
    childLog=$outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
