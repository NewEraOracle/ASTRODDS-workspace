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

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Get-DateKey($d) {
    try { return ([datetime]$d).ToString("yyyy-MM-dd") } catch { return (Get-Date).ToString("yyyy-MM-dd") }
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

$eliteCsv = Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv"
$inputCsv = Join-Path $astro "ASTRODDS-premium-input-starter-xfip.csv"
$outCsv = Join-Path $astro "ASTRODDS-359-starter-xfip-real-source-bridge-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-359-starter-xfip-real-source-bridge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-359-starter-xfip-real-source-bridge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 359 TRUE xFIP / ADVANCED STARTER IMPORT BRIDGE" -ForegroundColor Cyan
Write-Host "Reads real FanGraphs/export CSV. Missing xFIP remains MISSING_SOURCE; FIP proxy stays separate." -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $inputCsv)) {
    "Pitcher,Team,Throws,FIP,xFIP,KBBPercent,SIERA,Source,UpdatedAt" | Set-Content -Encoding UTF8 $inputCsv
}

$source = Safe-Csv $inputCsv
$elite = Safe-Csv $eliteCsv

function Find-Pitcher($name, $rows) {
    $nn = Normalize-Name $name
    foreach ($r in $rows) {
        if ((Normalize-Name (Get-Val $r @("Pitcher","Name","Player"))) -eq $nn) { return $r }
    }
    return $null
}

$out = @()

foreach ($g in $elite) {
    $game = Get-Val $g @("Game")
    $awayStarter = Get-Val $g @("AwayStarter","AwayPitcher")
    $homeStarter = Get-Val $g @("HomeStarter","HomePitcher")

    $away = if ($awayStarter -ne "") { Find-Pitcher $awayStarter $source } else { $null }
    $home = if ($homeStarter -ne "") { Find-Pitcher $homeStarter $source } else { $null }

    $awayStatus = if ($awayStarter -eq "") { "MISSING_STARTER_NAME" } elseif ($null -ne $away -and (Get-Val $away @("xFIP")) -ne "") { "CSV_TRUE_XFIP_CONNECTED" } else { "MISSING_XFIP_SOURCE" }
    $homeStatus = if ($homeStarter -eq "") { "MISSING_STARTER_NAME" } elseif ($null -ne $home -and (Get-Val $home @("xFIP")) -ne "") { "CSV_TRUE_XFIP_CONNECTED" } else { "MISSING_XFIP_SOURCE" }

    $out += ,[pscustomobject]@{
        Game=$game
        AwayStarter=$awayStarter
        HomeStarter=$homeStarter
        AwayXfipStatus=$awayStatus
        HomeXfipStatus=$homeStatus
        AwayFIP=Get-Val $away @("FIP")
        AwayxFIP=Get-Val $away @("xFIP")
        AwayKBBPercent=Get-Val $away @("KBBPercent","K-BB%","KBB%")
        AwaySIERA=Get-Val $away @("SIERA")
        HomeFIP=Get-Val $home @("FIP")
        HomexFIP=Get-Val $home @("xFIP")
        HomeKBBPercent=Get-Val $home @("KBBPercent","K-BB%","KBB%")
        HomeSIERA=Get-Val $home @("SIERA")
        AwaySource=Get-Val $away @("Source")
        HomeSource=Get-Val $home @("Source")
        InputCsv=$inputCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$any = @($out | Where-Object { $_.AwayXfipStatus -eq "CSV_TRUE_XFIP_CONNECTED" -or $_.HomeXfipStatus -eq "CSV_TRUE_XFIP_CONNECTED" }).Count
$full = @($out | Where-Object { $_.AwayXfipStatus -eq "CSV_TRUE_XFIP_CONNECTED" -and $_.HomeXfipStatus -eq "CSV_TRUE_XFIP_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 359 TRUE xFIP / ADVANCED STARTER IMPORT BRIDGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Rows with any true xFIP source: $any"
$lines += "Rows fully connected: $full"
$lines += "Input CSV template: $inputCsv"
$lines += ""
$lines += "RULE"
$lines += "- True xFIP only comes from CSV/export values."
$lines += "- FIP proxy remains separate; it is not renamed to xFIP."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Game) | away=$($r.AwayStarter) $($r.AwayXfipStatus) xFIP=$($r.AwayxFIP) | home=$($r.HomeStarter) $($r.HomeXfipStatus) xFIP=$($r.HomexFIP)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    rowsWithAnyTrueXfip=$any
    rowsFullyConnected=$full
    outputCsv=$outCsv
    inputCsv=$inputCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
