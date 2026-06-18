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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        return (Normalize-Team $parts[0]) + " @ " + (Normalize-Team $parts[1])
    }
    return (Normalize-Team $g)
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

function Find-By-Team($rows, $team) {
    $k = Normalize-Team $team
    foreach ($r in @($rows)) {
        $t = Get-Val $r @("Team","team","Name","name")
        if ((Normalize-Team $t) -eq $k) { return $r }
    }
    return $null
}

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

function Ip-To-Decimal($ipText) {
    $s = "$ipText".Trim()
    if ($s -eq "") { return $null }
    $parts = $s -split "\."
    $whole = 0
    $frac = 0
    try { $whole = [int]$parts[0] } catch { return $null }
    if ($parts.Count -gt 1) {
        try { $outs = [int]$parts[1]; $frac = $outs / 3.0 } catch { $frac = 0 }
    }
    return ($whole + $frac)
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$pitcherCsv = Join-Path $astro "ASTRODDS-starter-advanced-pitcher-metrics-latest.csv"
$sourceCsv = Join-Path $astro "ASTRODDS-platoon-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-platoon-splits-lr-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-318-platoon-splits-lr-context-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-318-platoon-splits-lr-context-latest.json"

Write-Host ""
Write-Host "ASTRODDS 318 PLATOON SPLITS LEFT/RIGHT CONTEXT" -ForegroundColor Cyan
Write-Host "No fake platoon splits. Uses optional ASTRODDS-platoon-source-latest.csv if present; starter handedness comes from 317." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv
$pitchers = Safe-Csv $pitcherCsv
$platoon = Safe-Csv $sourceCsv

function Get-Team-Platoon($team, $hand) {
    $row = Find-By-Team $platoon $team
    if ($null -eq $row) { return @("", "PLATOON_SOURCE_MISSING") }

    $h = "$hand".ToUpper()
    if ($h -eq "L") {
        $v = Get-Val $row @("VsLhpWrcPlus","VsLHP_wRCPlus","VsLeftWrcPlus","VsLhpOps","VsLHP_OPS")
        return @($v, "CONNECTED_VS_LHP")
    } elseif ($h -eq "R") {
        $v = Get-Val $row @("VsRhpWrcPlus","VsRHP_wRCPlus","VsRightWrcPlus","VsRhpOps","VsRHP_OPS")
        return @($v, "CONNECTED_VS_RHP")
    }
    return @("", "STARTER_HAND_UNKNOWN")
}

$out = @()
foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $p = Find-By-Game $pitchers $game

    $awayTeam = Get-Val $g @("AwayTeam")
    $homeTeam = Get-Val $g @("HomeTeam")
    $awayStarterHand = Get-Val $p @("AwayStarterHand")
    $homeStarterHand = Get-Val $p @("HomeStarterHand")

    # Away offense faces home starter. Home offense faces away starter.
    $awayPlatoon = Get-Team-Platoon $awayTeam $homeStarterHand
    $homePlatoon = Get-Team-Platoon $homeTeam $awayStarterHand

    $status = "PARTIAL_OR_MISSING"
    if ($awayPlatoon[1] -match "CONNECTED" -and $homePlatoon[1] -match "CONNECTED") { $status = "CONNECTED_PLATOON_SOURCE" }

    $out += ,[pscustomobject]@{
        Source = if ($status -eq "CONNECTED_PLATOON_SOURCE") { "USER_OR_EXTERNAL_PLATOON_SOURCE" } else { "PLATOON_SOURCE_SLOT" }
        Game = $game
        GamePk = Get-Val $g @("GamePk")
        AwayTeam = $awayTeam
        HomeTeam = $homeTeam
        AwayOffenseFacesHand = $homeStarterHand
        HomeOffenseFacesHand = $awayStarterHand
        AwayPlatoonValue = $awayPlatoon[0]
        HomePlatoonValue = $homePlatoon[0]
        AwayPlatoonStatus = $awayPlatoon[1]
        HomePlatoonStatus = $homePlatoon[1]
        PlatoonContextStatus = $status
        Note = "Add ASTRODDS-platoon-source-latest.csv with Team,VsLhpWrcPlus,VsRhpWrcPlus or OPS columns to connect this premium factor."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$connected = @($out | Where-Object { $_.PlatoonContextStatus -eq "CONNECTED_PLATOON_SOURCE" }).Count

$lines = @()
$lines += "ASTRODDS 318 PLATOON SPLITS LEFT/RIGHT CONTEXT"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Connected platoon rows: $connected"
$lines += "Missing/partial rows: $($out.Count - $connected)"
$lines += ""
$lines += "OPTIONAL SOURCE FORMAT"
$lines += "Create: .astrodds\ASTRODDS-platoon-source-latest.csv"
$lines += "Columns: Team,VsLhpWrcPlus,VsRhpWrcPlus"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.PlatoonContextStatus) | $($r.Game) | away faces $($r.AwayOffenseFacesHand) value=$($r.AwayPlatoonValue) | home faces $($r.HomeOffenseFacesHand) value=$($r.HomePlatoonValue)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
