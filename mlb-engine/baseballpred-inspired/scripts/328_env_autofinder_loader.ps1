$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Safe-Read($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Get-Content $path -ErrorAction Stop) } catch { return @() }
}

function Parse-EnvFile($path) {
    $rows = @()
    foreach ($line in (Safe-Read $path)) {
        if ($line -match "^\s*#") { continue }
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            $rows += ,[pscustomobject]@{ Name=$name; Value=$value }
        }
    }
    return @($rows)
}

function Load-EnvFromFile($path) {
    if (!(Test-Path $path)) { return $false }
    foreach ($r in (Parse-EnvFile $path)) {
        [Environment]::SetEnvironmentVariable($r.Name, $r.Value, "Process")
    }

    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
    if ($env:ASTRODDS_TELEGRAM_BOT_TOKEN -and -not $env:TELEGRAM_BOT_TOKEN) { $env:TELEGRAM_BOT_TOKEN = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
    if ($env:ASTRODDS_TELEGRAM_CHAT_ID -and -not $env:TELEGRAM_CHAT_ID) { $env:TELEGRAM_CHAT_ID = $env:ASTRODDS_TELEGRAM_CHAT_ID }

    return $true
}

function Score-EnvFile($path) {
    $score = 0
    $keys = Parse-EnvFile $path
    foreach ($r in $keys) {
        $n = $r.Name
        if ($n -match "ODDS_API|THE_ODDS|ASTRODDS_ODDS") { $score += 100 }
        if ($n -match "TELEGRAM.*TOKEN|BOT_TOKEN") { $score += 30 }
        if ($n -match "TELEGRAM.*CHAT|CHAT_ID") { $score += 30 }
        if ($n -match "ASTRODDS") { $score += 10 }
    }
    try { $score += [int]((Get-Item $path).LastWriteTime.Ticks % 1000) } catch {}
    return $score
}

function Find-BestEnvFile($root) {
    $candidates = @()

    $fixed = @(
        (Join-Path $root ".env.local"),
        (Join-Path $root ".env"),
        (Join-Path $root "mlb-engine\.env.local"),
        (Join-Path $root "mlb-engine\.env"),
        (Join-Path $root "mlb-engine\baseballpred-inspired\.env.local"),
        (Join-Path $root "mlb-engine\baseballpred-inspired\.env"),
        (Join-Path $env:USERPROFILE ".astrodds\.env"),
        (Join-Path $env:USERPROFILE ".env")
    )

    foreach ($p in $fixed) {
        if (Test-Path $p) { $candidates += (Get-Item $p) }
    }

    try {
        $recursive = Get-ChildItem $root -Recurse -Force -File -Include ".env",".env.local",".env.production","*.env" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\node_modules\\|\\.next\\|\\dist\\|\\build\\" }
        $candidates += @($recursive)
    } catch {}

    $unique = @{}
    foreach ($c in $candidates) { $unique[$c.FullName] = $c }

    $scored = @()
    foreach ($p in $unique.Keys) {
        $score = Score-EnvFile $p
        $scored += ,[pscustomobject]@{ Path=$p; Score=$score; LastWriteTime=(Get-Item $p).LastWriteTime }
    }

    $best = $scored | Sort-Object Score, LastWriteTime -Descending | Select-Object -First 1
    return $best
}

function Run-Step($name, $path, [ref]$childLog) {
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
        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exitCode"
        $childLog.Value += "DURATION: $duration sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })
        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$duration}
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exitCode";DurationSec=$duration}
        }
    } catch {
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-328-env-autofinder-loader-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-328-env-autofinder-loader-latest.json"
$runtimeLoader = Join-Path $astro "ASTRODDS-runtime-env-loader.ps1"
$envPointer = Join-Path $astro "ASTRODDS-env-source-path-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 328F ENV AUTOFINDER + RUNTIME LOADER FIXED" -ForegroundColor Cyan
Write-Host "Finds .env/.env.local without exposing secrets." -ForegroundColor Cyan
Write-Host ""

$best = Find-BestEnvFile $root
$loaded = $false
$keys = @()

if ($null -ne $best -and $best.Path -ne "") {
    $loaded = Load-EnvFromFile $best.Path
    $keys = Parse-EnvFile $best.Path
    $best.Path | Set-Content -Encoding UTF8 $envPointer
}

$loaderCode = @'
function Load-AstroddsRuntimeEnv {
    param(
        [string]$Root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
    )

    $pointer = Join-Path $Root ".astrodds\ASTRODDS-env-source-path-latest.txt"
    $candidates = @()

    if (Test-Path $pointer) {
        $p = (Get-Content $pointer -Raw).Trim()
        if ($p -ne "") { $candidates += $p }
    }

    $candidates += @(
        (Join-Path $Root ".env.local"),
        (Join-Path $Root ".env"),
        (Join-Path $Root "mlb-engine\.env.local"),
        (Join-Path $Root "mlb-engine\.env"),
        (Join-Path $Root "mlb-engine\baseballpred-inspired\.env.local"),
        (Join-Path $Root "mlb-engine\baseballpred-inspired\.env"),
        (Join-Path $env:USERPROFILE ".astrodds\.env"),
        (Join-Path $env:USERPROFILE ".env")
    )

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            Get-Content $path | ForEach-Object {
                if ($_ -match "^\s*#") { return }
                if ($_ -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") {
                    $name = $matches[1].Trim()
                    $value = $matches[2].Trim().Trim('"').Trim("'")
                    [Environment]::SetEnvironmentVariable($name, $value, "Process")
                }
            }

            if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
            if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
            if ($env:ASTRODDS_TELEGRAM_BOT_TOKEN -and -not $env:TELEGRAM_BOT_TOKEN) { $env:TELEGRAM_BOT_TOKEN = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
            if ($env:ASTRODDS_TELEGRAM_CHAT_ID -and -not $env:TELEGRAM_CHAT_ID) { $env:TELEGRAM_CHAT_ID = $env:ASTRODDS_TELEGRAM_CHAT_ID }

            return $path
        }
    }

    return ""
}
'@
$loaderCode | Set-Content -Encoding UTF8 $runtimeLoader

$keyNames = @("ODDS_API_KEY","THE_ODDS_API_KEY","ASTRODDS_ODDS_API_KEY","TELEGRAM_BOT_TOKEN","ASTRODDS_TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","ASTRODDS_TELEGRAM_CHAT_ID","ASTRODDS_TELEGRAM_SEND")
$present = @()
foreach ($k in $keyNames) {
    $v = [Environment]::GetEnvironmentVariable($k, "Process")
    $present += ,[pscustomobject]@{
        Name = $k
        Present = ([bool]$v)
        Length = if ($v) { $v.Length } else { 0 }
    }
}

$lines = @()
$lines += "ASTRODDS 328F ENV AUTOFINDER + RUNTIME LOADER FIXED"
$lines += ""
$lines += "Env found: $([bool]$best)"
if ($null -ne $best) { $lines += "Env source: $($best.Path)" }
$lines += "Env loaded into current process: $loaded"
$lines += "Runtime loader created: $runtimeLoader"
$lines += ""
$lines += "KEY STATUS - values hidden"
foreach ($p in $present) {
    $lines += "- $($p.Name): present=$($p.Present) length=$($p.Length)"
}
$lines += ""
$lines += "SAFETY"
$lines += "- No secret values are printed."
$lines += "- Telegram send remains dry-run unless ASTRODDS_TELEGRAM_SEND=YES."

$envSourceForJson = ""
if ($null -ne $best) { $envSourceForJson = $best.Path }

$envSourceForJson = ""
if ($null -ne $best) { $envSourceForJson = $best.Path }

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    envFound=([bool]$best)
    envSource=$envSourceForJson
    loaded=$loaded
    runtimeLoader=$runtimeLoader
    keyStatus=@($present)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0


