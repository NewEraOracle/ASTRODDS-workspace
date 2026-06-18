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

$inputCsv = Join-Path $astro "ASTRODDS-premium-input-team-platoon-splits.csv"
$bridgeCsv = Join-Path $astro "ASTRODDS-358-platoon-splits-real-source-bridge-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-371-platoon-real-csv-finalizer-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-371-platoon-real-csv-finalizer-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-371-platoon-real-csv-finalizer-latest.json"

Write-Host ""
Write-Host "ASTRODDS 371 PLATOON REAL CSV FINALIZER" -ForegroundColor Cyan
Write-Host "Finalizes real platoon source only if CSV/export has rows. No fake splits." -ForegroundColor Cyan
Write-Host ""

$input = Safe-Csv $inputCsv
$bridge = Safe-Csv $bridgeCsv

$validInput = @($input | Where-Object {
    (Get-Val $_ @("Team")) -ne "" -and
    (Get-Val $_ @("VsHand")) -match "L|R" -and
    ((Get-Val $_ @("wRCPlus","OPS","OBP","SLG")) -ne "") -and
    (Get-Val $_ @("Source")) -ne ""
})

$out = @()
foreach ($r in $bridge) {
    $away = Get-Val $r @("AwayPlatoonStatus")
    $home = Get-Val $r @("HomePlatoonStatus")
    $status = "MISSING_SOURCE"
    if ($away -eq "CSV_REAL_PLATOON_CONNECTED" -and $home -eq "CSV_REAL_PLATOON_CONNECTED") { $status = "FULL_REAL_PLATOON_CONNECTED" }
    elseif ($away -eq "CSV_REAL_PLATOON_CONNECTED" -or $home -eq "CSV_REAL_PLATOON_CONNECTED") { $status = "PARTIAL_REAL_PLATOON_CONNECTED" }

    $out += ,[pscustomobject]@{
        Game=Get-Val $r @("Game")
        RealPlatoonFinalStatus=$status
        AwayPlatoonStatus=$away
        HomePlatoonStatus=$home
        AwayWRCPlus=Get-Val $r @("AwayWRCPlus")
        HomeWRCPlus=Get-Val $r @("HomeWRCPlus")
        AwayOPS=Get-Val $r @("AwayOPS")
        HomeOPS=Get-Val $r @("HomeOPS")
        SourceCsv=$inputCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$full = @($out | Where-Object { $_.RealPlatoonFinalStatus -eq "FULL_REAL_PLATOON_CONNECTED" }).Count
$partial = @($out | Where-Object { $_.RealPlatoonFinalStatus -eq "PARTIAL_REAL_PLATOON_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 371 PLATOON REAL CSV FINALIZER"
$lines += ""
$lines += "Valid source rows: $($validInput.Count)"
$lines += "Full real platoon games: $full"
$lines += "Partial real platoon games: $partial"
$lines += "Input CSV: $inputCsv"
$lines += ""
$lines += "RULE"
$lines += "- Platoon is connected only from real CSV/export rows."
$lines += "- Blank CSV = MISSING_SOURCE."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.RealPlatoonFinalStatus) | $($r.Game)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    validSourceRows=$validInput.Count
    fullRealPlatoonGames=$full
    partialRealPlatoonGames=$partial
    outputCsv=$outCsv
    inputCsv=$inputCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
