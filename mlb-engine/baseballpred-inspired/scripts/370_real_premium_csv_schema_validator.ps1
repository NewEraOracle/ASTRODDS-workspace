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

$files = @(
    [pscustomobject]@{
        Name="Platoon splits"
        Path=(Join-Path $astro "ASTRODDS-premium-input-team-platoon-splits.csv")
        Header="Team,VsHand,wRCPlus,OPS,OBP,SLG,KPercent,BBPercent,Source,UpdatedAt"
        Required=@("Team","VsHand","wRCPlus","OPS","Source")
    },
    [pscustomobject]@{
        Name="Starter xFIP"
        Path=(Join-Path $astro "ASTRODDS-premium-input-starter-xfip.csv")
        Header="Pitcher,Team,Throws,FIP,xFIP,KBBPercent,SIERA,Source,UpdatedAt"
        Required=@("Pitcher","Team","FIP","xFIP","KBBPercent","Source")
    },
    [pscustomobject]@{
        Name="True bullpen leverage"
        Path=(Join-Path $astro "ASTRODDS-premium-input-bullpen-leverage-availability.csv")
        Header="Team,Reliever,Role,LeverageIndex,AvailabilityStatus,Source,UpdatedAt"
        Required=@("Team","Reliever","Role","LeverageIndex","AvailabilityStatus","Source")
    },
    [pscustomobject]@{
        Name="Umpire ratings"
        Path=(Join-Path $astro "ASTRODDS-premium-input-umpire-ratings.csv")
        Header="HomePlateUmpire,UmpireRunsPlusMinus,OverPct,HomeWinPct,StrikeZoneGrade,Source,UpdatedAt"
        Required=@("HomePlateUmpire","Source")
    }
)

$outTxt = Join-Path $astro "ASTRODDS-370-real-premium-csv-schema-validator-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-370-real-premium-csv-schema-validator-latest.json"

Write-Host ""
Write-Host "ASTRODDS 370 REAL PREMIUM CSV SCHEMA VALIDATOR" -ForegroundColor Cyan
Write-Host "Creates templates and validates real CSV/API exports. Empty = not connected, not fake." -ForegroundColor Cyan
Write-Host ""

$results = @()

foreach ($f in $files) {
    if (!(Test-Path $f.Path)) {
        $f.Header | Set-Content -Encoding UTF8 $f.Path
    }

    $rows = Safe-Csv $f.Path
    $headers = @()
    try { $headers = @((Import-Csv $f.Path -TotalCount 1).PSObject.Properties.Name) } catch {
        try { $headers = @(((Get-Content $f.Path -First 1) -split ",")) } catch {}
    }

    $missing = @()
    foreach ($req in $f.Required) {
        if ($headers -notcontains $req) { $missing += $req }
    }

    $nonEmptyRows = @($rows | Where-Object {
        $has = $false
        foreach ($p in $_.PSObject.Properties) {
            if ("$($p.Value)".Trim() -ne "") { $has = $true; break }
        }
        $has
    })

    $status = "TEMPLATE_EMPTY_NOT_CONNECTED"
    if ($missing.Count -gt 0) { $status = "SCHEMA_MISSING_COLUMNS" }
    elseif ($nonEmptyRows.Count -gt 0) { $status = "REAL_CSV_ROWS_AVAILABLE" }

    $results += ,[pscustomobject]@{
        Name=$f.Name
        Path=$f.Path
        Status=$status
        Rows=$nonEmptyRows.Count
        MissingColumns=($missing -join "|")
        RequiredColumns=($f.Required -join "|")
    }
}

$lines = @()
$lines += "ASTRODDS 370 REAL PREMIUM CSV SCHEMA VALIDATOR"
$lines += ""
foreach ($r in $results) {
    $lines += "- $($r.Status) | $($r.Name) | rows=$($r.Rows) | missing=$($r.MissingColumns)"
    $lines += "  $($r.Path)"
}
$lines += ""
$lines += "NO-FAKE RULE"
$lines += "- Empty templates do not create data."
$lines += "- Invalid schemas are blocked."
$lines += "- Only real filled rows are connected."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    results=@($results)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
