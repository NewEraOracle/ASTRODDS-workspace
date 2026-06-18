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

function Set-Prop($obj, $name, $value) {
    if ($obj.PSObject.Properties[$name]) {
        $obj.$name = $value
    } else {
        $obj | Add-Member -MemberType NoteProperty -Name $name -Value $value -Force
    }
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
        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-329-run-final-with-env-autoload-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-329-run-final-with-env-autoload-latest.json"
$outChild = Join-Path $astro "ASTRODDS-329-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 329B RUN FINAL WITH ENV AUTOLOAD + 351 SYNC" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "328 env autofinder" (Join-Path $scripts "328_env_autofinder_loader.ps1") $ref)

$runtime = Join-Path $astro "ASTRODDS-runtime-env-loader.ps1"
$envSource = ""
if (Test-Path $runtime) {
    . $runtime
    $envSource = Load-AstroddsRuntimeEnv $root
}

$steps += ,(Run-Step "308 final production one-command" (Join-Path $scripts "308_final_production_one_command.ps1") $ref)
$steps += ,(Run-Step "351 final settlement/training sync" (Join-Path $scripts "351_final_settlement_training_sync.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$readiness = Join-Path $astro "ASTRODDS-312-final-readiness-gate-latest.txt"
$clientText = ""
$readyText = ""
if (Test-Path $client) { $clientText = Get-Content $client -Raw }
if (Test-Path $readiness) { $readyText = Get-Content $readiness -Raw }

$lines = @()
$lines += "ASTRODDS 329B RUN FINAL WITH ENV AUTOLOAD + 351 SYNC"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Env source loaded: $envSource"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "READINESS"
$lines += $readyText
$lines += ""
$lines += "CLIENT"
$lines += $clientText

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    envSource=$envSource
    steps=@($steps)
    childLog=$outChild
    clientReport=$client
    readiness=$readiness
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
