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

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
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
        $exit = $LASTEXITCODE
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exit"
        $childLog.Value += "DURATION: $dur sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
        } else {
            Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
        }
    } catch {
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-376-230AM-AND-REAL-PREMIUM-FINISH-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-376-230AM-AND-REAL-PREMIUM-FINISH-RUN-latest.json"
$outChild = Join-Path $astro "ASTRODDS-376-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 376 2:30AM + REAL PREMIUM FINISH RUNNER" -ForegroundColor Cyan
Write-Host "Finalizes moneyline send guard, 2:30 report, and real premium source bridges." -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "351 final sync + 2:30AM + real premium finish" (Join-Path $scripts "351_final_settlement_training_sync.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$guardTxt = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt"
$premiumTxt = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$milestoneTxt = Join-Path $astro "ASTRODDS-374-settled-results-milestone-promoter-latest.txt"
$schemaTxt = Join-Path $astro "ASTRODDS-370-real-premium-csv-schema-validator-latest.txt"

$guard = ""; $premium = ""; $milestone = ""; $schema = ""
if (Test-Path $guardTxt) { $guard = Get-Content $guardTxt -Raw }
if (Test-Path $premiumTxt) { $premium = Get-Content $premiumTxt -Raw }
if (Test-Path $milestoneTxt) { $milestone = Get-Content $milestoneTxt -Raw }
if (Test-Path $schemaTxt) { $schema = Get-Content $schemaTxt -Raw }

$lines = @()
$lines += "ASTRODDS 376 2:30AM + REAL PREMIUM FINISH RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "MONEYLINE / 2:30AM"
$lines += $guard
$lines += ""
$lines += "MILESTONES"
$lines += $milestone
$lines += ""
$lines += "REAL PREMIUM CSV STATUS"
$lines += $schema
$lines += ""
$lines += "PREMIUM"
$lines += $premium
$lines += ""
$lines += "VERDICT"
$lines += "- Moneyline send remains pre-game only."
$lines += "- 2:30 AM is daily report only."
$lines += "- Platoon/xFIP/leverage finish only when real CSV/API rows are provided."
$lines += "- 75/150 settled picks cannot be invented; milestone tracker is active."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    guardReport=$guardTxt
    premiumReport=$premiumTxt
    milestoneReport=$milestoneTxt
    schemaReport=$schemaTxt
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
