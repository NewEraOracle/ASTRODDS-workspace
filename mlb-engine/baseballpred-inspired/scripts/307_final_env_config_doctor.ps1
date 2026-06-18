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
    if ($env:ASTRODDS_TELEGRAM_BOT_TOKEN -and -not $env:TELEGRAM_BOT_TOKEN) { $env:TELEGRAM_BOT_TOKEN = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
    if ($env:ASTRODDS_TELEGRAM_CHAT_ID -and -not $env:TELEGRAM_CHAT_ID) { $env:TELEGRAM_CHAT_ID = $env:ASTRODDS_TELEGRAM_CHAT_ID }
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
        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro
Load-EnvLocal $root

$outTxt = Join-Path $astro "ASTRODDS-307-final-env-config-doctor-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-307-final-env-config-doctor-latest.json"

Write-Host ""
Write-Host "ASTRODDS 307 FINAL ENV / CONFIG DOCTOR" -ForegroundColor Cyan
Write-Host ""

$requiredScripts = @(
    "324_run_elite_factors_runner.ps1",
    "306_baseballpred_plus_runner_with_aliases.ps1",
    "283_credit_safe_pregame_rescan.ps1",
    "297_telegram_auto_send_safe.ps1",
    "323_elite_official_gate.ps1",
    "325_elite_factors_report.ps1"
)

$scriptChecks = @()
foreach ($s in $requiredScripts) {
    $p = Join-Path $scripts $s
    $scriptChecks += ,[pscustomobject]@{ Script=$s; Exists=(Test-Path $p); Path=$p }
}

$configRows = @(
    [pscustomobject]@{ Name="ODDS_API_KEY"; Loaded=([bool]$env:ODDS_API_KEY); Note="External moneyline odds. Key hidden." },
    [pscustomobject]@{ Name="TELEGRAM_BOT_TOKEN"; Loaded=([bool]$env:TELEGRAM_BOT_TOKEN); Note="Only needed if real Telegram send enabled." },
    [pscustomobject]@{ Name="TELEGRAM_CHAT_ID"; Loaded=([bool]$env:TELEGRAM_CHAT_ID); Note="Only needed if real Telegram send enabled." },
    [pscustomobject]@{ Name="ASTRODDS_TELEGRAM_SEND"; Loaded=($env:ASTRODDS_TELEGRAM_SEND -eq "YES"); Note="YES = real send. Other = dry-run." },
    [pscustomobject]@{ Name="ASTRODDS_ODDS_MONTHLY_LIMIT"; Loaded=([bool]$env:ASTRODDS_ODDS_MONTHLY_LIMIT); Note="Default 500 if empty." },
    [pscustomobject]@{ Name="ASTRODDS_SCAN_INTERVAL_MINUTES"; Loaded=([bool]$env:ASTRODDS_SCAN_INTERVAL_MINUTES); Note="Default 10 if empty." }
)

$missingScripts = @($scriptChecks | Where-Object { -not $_.Exists }).Count
$ready = ($missingScripts -eq 0)

$lines = @()
$lines += "ASTRODDS 307 FINAL ENV / CONFIG DOCTOR"
$lines += ""
$lines += "Ready for production runner: $ready"
$lines += "Missing required scripts: $missingScripts"
$lines += ""
$lines += "CONFIG"
foreach ($c in $configRows) { $lines += "- $($c.Name): $($c.Loaded) | $($c.Note)" }
$lines += ""
$lines += "SCRIPTS"
foreach ($s in $scriptChecks) { $lines += "- $($s.Script): $($s.Exists)" }
$lines += ""
$lines += "SAFETY"
$lines += "- Telegram real send is OFF unless ASTRODDS_TELEGRAM_SEND=YES."
$lines += "- No new drop is allowed after game start."
$lines += "- Elite gate still blocks if line-shopping does not pass."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    ready=$ready
    missingScripts=$missingScripts
    configs=@($configRows)
    scripts=@($scriptChecks)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
