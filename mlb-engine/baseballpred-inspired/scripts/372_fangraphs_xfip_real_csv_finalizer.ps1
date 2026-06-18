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

$inputCsv = Join-Path $astro "ASTRODDS-premium-input-starter-xfip.csv"
$bridgeCsv = Join-Path $astro "ASTRODDS-359-starter-xfip-real-source-bridge-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-372-fangraphs-xfip-real-csv-finalizer-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-372-fangraphs-xfip-real-csv-finalizer-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-372-fangraphs-xfip-real-csv-finalizer-latest.json"

Write-Host ""
Write-Host "ASTRODDS 372 FANGRAPHS xFIP REAL CSV FINALIZER" -ForegroundColor Cyan
Write-Host "Finalizes true xFIP only if FanGraphs/export CSV has real rows. No xFIP proxy." -ForegroundColor Cyan
Write-Host ""

$input = Safe-Csv $inputCsv
$bridge = Safe-Csv $bridgeCsv

$validInput = @($input | Where-Object {
    (Get-Val $_ @("Pitcher")) -ne "" -and
    (Get-Val $_ @("xFIP")) -ne "" -and
    (Get-Val $_ @("Source")) -ne ""
})

$out = @()
foreach ($r in $bridge) {
    $away = Get-Val $r @("AwayXfipStatus")
    $home = Get-Val $r @("HomeXfipStatus")
    $status = "MISSING_SOURCE"
    if ($away -eq "CSV_TRUE_XFIP_CONNECTED" -and $home -eq "CSV_TRUE_XFIP_CONNECTED") { $status = "FULL_TRUE_XFIP_CONNECTED" }
    elseif ($away -eq "CSV_TRUE_XFIP_CONNECTED" -or $home -eq "CSV_TRUE_XFIP_CONNECTED") { $status = "PARTIAL_TRUE_XFIP_CONNECTED" }

    $out += ,[pscustomobject]@{
        Game=Get-Val $r @("Game")
        TrueXfipFinalStatus=$status
        AwayStarter=Get-Val $r @("AwayStarter")
        HomeStarter=Get-Val $r @("HomeStarter")
        AwayxFIP=Get-Val $r @("AwayxFIP")
        HomexFIP=Get-Val $r @("HomexFIP")
        AwayKBBPercent=Get-Val $r @("AwayKBBPercent")
        HomeKBBPercent=Get-Val $r @("HomeKBBPercent")
        SourceCsv=$inputCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$full = @($out | Where-Object { $_.TrueXfipFinalStatus -eq "FULL_TRUE_XFIP_CONNECTED" }).Count
$partial = @($out | Where-Object { $_.TrueXfipFinalStatus -eq "PARTIAL_TRUE_XFIP_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 372 FANGRAPHS xFIP REAL CSV FINALIZER"
$lines += ""
$lines += "Valid source rows: $($validInput.Count)"
$lines += "Full true xFIP games: $full"
$lines += "Partial true xFIP games: $partial"
$lines += "Input CSV: $inputCsv"
$lines += ""
$lines += "RULE"
$lines += "- True xFIP is connected only from real CSV/export rows."
$lines += "- FIP proxy is not renamed to xFIP."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.TrueXfipFinalStatus) | $($r.Game) | away=$($r.AwayStarter) xFIP=$($r.AwayxFIP) | home=$($r.HomeStarter) xFIP=$($r.HomexFIP)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    validSourceRows=$validInput.Count
    fullTrueXfipGames=$full
    partialTrueXfipGames=$partial
    outputCsv=$outCsv
    inputCsv=$inputCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
