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
Ensure-Dir $astro

$inputCsv = Join-Path $astro "ASTRODDS-premium-input-bullpen-leverage-availability.csv"
$bullpenCsv = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-373-true-leverage-real-csv-finalizer-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-373-true-leverage-real-csv-finalizer-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-373-true-leverage-real-csv-finalizer-latest.json"

Write-Host ""
Write-Host "ASTRODDS 373 TRUE LEVERAGE REAL CSV FINALIZER" -ForegroundColor Cyan
Write-Host "Finalizes true leverage only from real CSV/export rows. No fake LI." -ForegroundColor Cyan
Write-Host ""

$input = Safe-Csv $inputCsv
$bullpen = Safe-Csv $bullpenCsv

$validInput = @($input | Where-Object {
    (Get-Val $_ @("Team")) -ne "" -and
    (Get-Val $_ @("Reliever")) -ne "" -and
    (Get-Val $_ @("LeverageIndex")) -ne "" -and
    (Get-Val $_ @("Source")) -ne ""
})

function Team-Match($a, $b) {
    $na = Normalize-Name $a
    $nb = Normalize-Name $b
    if ($na -eq "" -or $nb -eq "") { return $false }
    if ($na -eq $nb) { return $true }
    if ($na.Contains($nb) -or $nb.Contains($na)) { return $true }
    $aw = @($na -split " ")
    $bw = @($nb -split " ")
    return ($aw[$aw.Count-1] -eq $bw[$bw.Count-1])
}

$out = @()
foreach ($b in $bullpen) {
    $team = Get-Val $b @("Team")
    $teamRows = @($validInput | Where-Object { Team-Match (Get-Val $_ @("Team")) $team })
    $avgLi = ""
    if ($teamRows.Count -gt 0) {
        $sum = 0.0; $cnt = 0
        foreach ($r in $teamRows) {
            $n = Num (Get-Val $r @("LeverageIndex"))
            if ($null -ne $n) { $sum += $n; $cnt++ }
        }
        if ($cnt -gt 0) { $avgLi = [math]::Round($sum / $cnt, 3) }
    }

    $status = if ($teamRows.Count -gt 0) { "TRUE_LEVERAGE_CSV_CONNECTED" } else { "MISSING_TRUE_LEVERAGE_SOURCE" }

    $out += ,[pscustomobject]@{
        Team=$team
        TrueLeverageFinalStatus=$status
        LeverageRows=$teamRows.Count
        AverageLeverageIndex=$avgLi
        PitchUsageStatus=Get-Val $b @("PitchUsageStatus")
        CalibratedStress=Get-Val $b @("BullpenStressFromRealUsage","BullpenStressFromRealPitches")
        SourceCsv=$inputCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connectedTeams = @($out | Where-Object { $_.TrueLeverageFinalStatus -eq "TRUE_LEVERAGE_CSV_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 373 TRUE LEVERAGE REAL CSV FINALIZER"
$lines += ""
$lines += "Valid source rows: $($validInput.Count)"
$lines += "Connected teams: $connectedTeams"
$lines += "Input CSV: $inputCsv"
$lines += ""
$lines += "RULE"
$lines += "- True leverage is connected only from real CSV/export rows."
$lines += "- Missing leverage stays MISSING_TRUE_LEVERAGE_SOURCE."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.TrueLeverageFinalStatus) | $($r.Team) | rows=$($r.LeverageRows) | avgLI=$($r.AverageLeverageIndex)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    validSourceRows=$validInput.Count
    connectedTeams=$connectedTeams
    outputCsv=$outCsv
    inputCsv=$inputCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
