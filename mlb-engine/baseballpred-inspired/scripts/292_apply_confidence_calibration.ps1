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
Ensure-Dir $astro

$candidateCsv = Join-Path $astro "ASTRODDS-potential-candidate-board-latest.csv"
$calCsv = Join-Path $astro "ASTRODDS-confidence-calibration-policy-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-292-calibrated-candidate-board-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-292-apply-confidence-calibration-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-292-apply-confidence-calibration-latest.json"

Write-Host ""
Write-Host "ASTRODDS 292 APPLY CONFIDENCE CALIBRATION" -ForegroundColor Cyan
Write-Host ""

$candidates = Safe-Csv $candidateCsv
$cal = Safe-Csv $calCsv
$out = @()

function Adj-For-Confidence($confidence) {
    $c = Num $confidence
    if ($null -eq $c) { return 0 }
    foreach ($b in $cal) {
        $name = Get-Val $b @("ConfidenceBin")
        if ($name -match "(\d+)-(\d+)") {
            $lo = [int]$matches[1]
            $hi = [int]$matches[2]
            if ($c -ge $lo -and $c -le $hi) {
                $a = Num (Get-Val $b @("ConfidenceAdjustment"))
                if ($null -ne $a) { return $a }
            }
        }
    }
    return 0
}

foreach ($r in $candidates) {
    $conf = Num (Get-Val $r @("Confidence"))
    if ($null -eq $conf) { $conf = 60 }
    $adj = Adj-For-Confidence $conf
    $calConf = Clamp ($conf + $adj) 1 99

    $out += ,[pscustomobject]@{
        CandidateLevel = Get-Val $r @("CandidateLevel")
        CandidateScore = Get-Val $r @("CandidateScore")
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        MlbStatus = Get-Val $r @("MlbStatus")
        ModelProbability = Get-Val $r @("ModelProbability")
        Edge = Get-Val $r @("Edge")
        RawConfidence = [int][math]::Round($conf,0)
        CalibrationAdjustment = $adj
        CalibratedConfidence = [int][math]::Round($calConf,0)
        Lineups = Get-Val $r @("Lineups")
        MarketRowsFound = Get-Val $r @("MarketRowsFound")
        Reasons = Get-Val $r @("Reasons")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 292 APPLY CONFIDENCE CALIBRATION"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += ""
foreach ($r in ($out | Sort-Object CalibratedConfidence -Descending | Select-Object -First 12)) {
    $lines += "- $($r.Pick) | $($r.Game) | raw=$($r.RawConfidence) adj=$($r.CalibrationAdjustment) calibrated=$($r.CalibratedConfidence) | model=$($r.ModelProbability) | edge=$($r.Edge)"
}

[pscustomobject]@{ generatedAt=(Get-Date).ToString("o"); rows=$out.Count; outputCsv=$outCsv } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
