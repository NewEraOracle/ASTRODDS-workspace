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

$plusCsv = Join-Path $astro "ASTRODDS-baseballpred-plus-context-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-320-elite-factor-context-merge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-320-elite-factor-context-merge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 320 ELITE FACTOR CONTEXT MERGE" -ForegroundColor Cyan
Write-Host ""

$plus = Safe-Csv $plusCsv
$ump = Safe-Csv (Join-Path $astro "ASTRODDS-umpire-strike-zone-context-latest.csv")
$pitch = Safe-Csv (Join-Path $astro "ASTRODDS-starter-advanced-pitcher-metrics-latest.csv")
$plat = Safe-Csv (Join-Path $astro "ASTRODDS-platoon-splits-lr-context-latest.csv")
$bull = Safe-Csv (Join-Path $astro "ASTRODDS-bullpen-leverage-enhanced-latest.csv")

$out = @()
foreach ($g in $plus) {
    $game = Get-Val $g @("Game")
    $u = Find-By-Game $ump $game
    $p = Find-By-Game $pitch $game
    $pl = Find-By-Game $plat $game
    $b = Find-By-Game $bull $game

    $missing = @()
    $warn = @()

    if ($null -eq $u -or (Get-Val $u @("UmpireContextStatus")) -ne "UMPIRE_SOURCE_CONNECTED") { $warn += "umpire_not_connected" }
    if ($null -eq $p -or ((Get-Val $p @("AwayPitcherStatus")) -ne "CONNECTED_STATSAPI" -and (Get-Val $p @("HomePitcherStatus")) -ne "CONNECTED_STATSAPI")) { $missing += "starter_advanced_metrics" }
    if ($null -eq $pl -or (Get-Val $pl @("PlatoonContextStatus")) -ne "CONNECTED_PLATOON_SOURCE") { $warn += "platoon_source_not_connected" }
    if ($null -eq $b) { $missing += "enhanced_bullpen_leverage" }

    $status = "ELITE_CONTEXT_CONNECTED"
    if ($missing.Count -gt 0) { $status = "ELITE_CONTEXT_MISSING_CORE" }
    elseif ($warn.Count -gt 0) { $status = "ELITE_CONTEXT_PARTIAL_PREMIUM_WARNINGS" }

    $out += ,[pscustomobject]@{
        EliteContextStatus = $status
        Game = $game
        Pick = Get-Val $g @("Pick")
        MlbStatus = Get-Val $g @("MlbStatus")
        ModelProbability = Get-Val $g @("ModelProbability")
        CalibratedConfidence = Get-Val $g @("CalibratedConfidence")
        BestEntry = Get-Val $g @("BestEntry")
        BestBook = Get-Val $g @("BestBook")
        EdgeVsBest = Get-Val $g @("EdgeVsBest")
        PlusStatus = Get-Val $g @("PlusStatus")
        HomePlateUmpire = Get-Val $u @("HomePlateUmpire")
        UmpireStatus = Get-Val $u @("UmpireContextStatus")
        AwayStarter = Get-Val $p @("AwayStarter")
        AwayStarterHand = Get-Val $p @("AwayStarterHand")
        AwayFIPProxy = Get-Val $p @("AwayFIPProxy")
        AwayKMinusBBPctProxy = Get-Val $p @("AwayKMinusBBPctProxy")
        HomeStarter = Get-Val $p @("HomeStarter")
        HomeStarterHand = Get-Val $p @("HomeStarterHand")
        HomeFIPProxy = Get-Val $p @("HomeFIPProxy")
        HomeKMinusBBPctProxy = Get-Val $p @("HomeKMinusBBPctProxy")
        PlatoonStatus = Get-Val $pl @("PlatoonContextStatus")
        AwayReliefStressLevel = Get-Val $b @("AwayReliefStressLevel")
        HomeReliefStressLevel = Get-Val $b @("HomeReliefStressLevel")
        MissingEliteCore = ($missing -join "|")
        PremiumWarnings = ($warn -join "|")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$coreConnected = @($out | Where-Object { $_.EliteContextStatus -ne "ELITE_CONTEXT_MISSING_CORE" }).Count
$full = @($out | Where-Object { $_.EliteContextStatus -eq "ELITE_CONTEXT_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 320 ELITE FACTOR CONTEXT MERGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Core connected rows: $coreConnected"
$lines += "Full elite connected rows: $full"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.EliteContextStatus) | $($r.Pick) | $($r.Game) | edge=$($r.EdgeVsBest) | awaySP=$($r.AwayStarter) FIPp=$($r.AwayFIPProxy) | homeSP=$($r.HomeStarter) FIPp=$($r.HomeFIPProxy) | warn=$($r.PremiumWarnings)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
