$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-286-baseballpred-advanced-gap-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-286-baseballpred-advanced-gap-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-286-baseballpred-advanced-gap-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 286 BASEBALLPRED ADVANCED GAP AUDIT" -ForegroundColor Cyan
Write-Host ""


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

$checks = @(
    @{Factor="Live lineups"; Current="CONNECTED"; Importance="HIGH"; NextFix="Already connected via MLB feed/live"},
    @{Factor="Moneyline odds"; Current="CONNECTED"; Importance="HIGH"; NextFix="Connected via The Odds API + fallback"},
    @{Factor="Weather temperature/wind/rain"; Current="CONNECTED"; Importance="HIGH"; NextFix="Connected via Open-Meteo"},
    @{Factor="Probable pitchers"; Current="CONNECTED"; Importance="HIGH"; NextFix="Connected via MLB schedule hydrate probablePitcher"},
    @{Factor="Rolling bullpen fatigue 3d/7d"; Current="CONNECTED_PROXY"; Importance="HIGH"; NextFix="Improve with innings/pitches/leverage, not just pitchers-used count"},
    @{Factor="Injury / roster / IL"; Current="CONNECTED_PROXY"; Importance="HIGH"; NextFix="Upgrade with premium injury data or player-impact weights"},
    @{Factor="Ballpark altitude / elevation"; Current="MISSING"; Importance="MEDIUM"; NextFix="Add static ballpark altitude table; affects run environment more than moneyline"},
    @{Factor="Park dimensions / run factor"; Current="MISSING"; Importance="MEDIUM"; NextFix="Add static park factor table by stadium"},
    @{Factor="Roof open/closed"; Current="MISSING"; Importance="MEDIUM"; NextFix="Add roof status source for retractable stadiums"},
    @{Factor="Wind direction relative to field"; Current="MISSING"; Importance="MEDIUM"; NextFix="Add stadium orientation table and vector wind calculation"},
    @{Factor="Umpire / strike zone"; Current="MISSING"; Importance="MEDIUM"; NextFix="Needs probable home plate umpire source"},
    @{Factor="Travel/rest/time zone"; Current="PARTIAL_MISSING"; Importance="MEDIUM"; NextFix="Calculate from schedule history and distance/time zone"},
    @{Factor="Platoon splits L/R"; Current="MISSING"; Importance="HIGH"; NextFix="Needs player/team split stats source"},
    @{Factor="Starter quality advanced metrics"; Current="PARTIAL_MISSING"; Importance="HIGH"; NextFix="Needs ERA/FIP/xFIP/K-BB/handedness source"},
    @{Factor="CLV tracking"; Current="PARTIAL"; Importance="HIGH"; NextFix="Store closing price from odds source before first pitch"},
    @{Factor="Settled ROI/Brier/logloss"; Current="CONNECTED_PARTIAL"; Importance="HIGH"; NextFix="Runs after games final; needs volume"}
)

$out = @()
foreach ($c in $checks) {
    $out += ,[pscustomobject]@{
        Factor = $c.Factor
        CurrentStatus = $c.Current
        Importance = $c.Importance
        NextFix = $c.NextFix
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$lines = @()
$lines += "ASTRODDS 286 BASEBALLPRED ADVANCED GAP AUDIT"
$lines += ""
$lines += "CONNECTED / PARTIAL / MISSING"
foreach ($r in $out) {
    $lines += "- $($r.CurrentStatus) | $($r.Importance) | $($r.Factor)"
    $lines += "  Next: $($r.NextFix)"
}
$lines += ""
$lines += "BOTTOM LINE"
$lines += "- ASTRODDS now has the production structure and core sources."
$lines += "- To match very advanced BaseballPred-style factors, the next mathematical additions are altitude/park factor, wind direction vector, umpire, travel/rest, platoon splits, and advanced pitcher metrics."

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
