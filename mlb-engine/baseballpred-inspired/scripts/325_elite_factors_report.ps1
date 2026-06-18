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

$outTxt = Join-Path $astro "ASTRODDS-325-elite-factors-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-325-elite-factors-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 325 ELITE FACTORS REPORT" -ForegroundColor Cyan
Write-Host ""

$ump = Safe-Csv (Join-Path $astro "ASTRODDS-umpire-strike-zone-context-latest.csv")
$pitch = Safe-Csv (Join-Path $astro "ASTRODDS-starter-advanced-pitcher-metrics-latest.csv")
$plat = Safe-Csv (Join-Path $astro "ASTRODDS-platoon-splits-lr-context-latest.csv")
$bull = Safe-Csv (Join-Path $astro "ASTRODDS-bullpen-leverage-enhanced-latest.csv")
$elite = Safe-Csv (Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv")
$gate = Safe-Csv (Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.csv")
$train = ""
$trainTxt = Join-Path $astro "ASTRODDS-322-train-model-when-ready-policy-latest.txt"
if (Test-Path $trainTxt) { $train = Get-Content $trainTxt -Raw }

$umpConnected = @($ump | Where-Object { (Get-Val $_ @("UmpireContextStatus")) -eq "UMPIRE_SOURCE_CONNECTED" }).Count
$pitchConnected = @($pitch | Where-Object { (Get-Val $_ @("AwayPitcherStatus")) -eq "CONNECTED_STATSAPI" -or (Get-Val $_ @("HomePitcherStatus")) -eq "CONNECTED_STATSAPI" }).Count
$platoonConnected = @($plat | Where-Object { (Get-Val $_ @("PlatoonContextStatus")) -eq "CONNECTED_PLATOON_SOURCE" }).Count
$eliteFull = @($elite | Where-Object { (Get-Val $_ @("EliteContextStatus")) -eq "ELITE_CONTEXT_CONNECTED" }).Count
$eliteCore = @($elite | Where-Object { (Get-Val $_ @("EliteContextStatus")) -ne "ELITE_CONTEXT_MISSING_CORE" }).Count
$send = @($gate | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "CLIENT_OFFICIAL_ELITE_SEND_OK" }).Count

$lines = @()
$lines += "ASTRODDS 325 ELITE FACTORS REPORT"
$lines += ""
$lines += "ELITE FACTOR STATUS"
$lines += "- Umpire connected rows: $umpConnected / $($ump.Count)"
$lines += "- Starter advanced metrics connected rows: $pitchConnected / $($pitch.Count)"
$lines += "- Platoon source connected rows: $platoonConnected / $($plat.Count)"
$lines += "- Enhanced bullpen leverage rows: $($bull.Count)"
$lines += "- Elite core connected rows: $eliteCore / $($elite.Count)"
$lines += "- Full elite connected rows: $eliteFull / $($elite.Count)"
$lines += "- Elite SEND_OK: $send"
$lines += ""
$lines += "WHAT IS REALLY CONNECTED NOW"
$lines += "- Starter handedness + season pitching stats via MLB StatsAPI"
$lines += "- FIP proxy, K-BB% proxy, ERA, WHIP"
$lines += "- Enhanced bullpen close-game/usage stress proxy"
$lines += "- Umpire source slot without fake data"
$lines += "- Platoon source slot without fake data"
$lines += "- Training dataset + model promotion policy"
$lines += ""
$lines += "WHAT STILL NEEDS EXTERNAL/PREMIUM DATA TO BE TRUE ELITE"
$lines += "- Confirmed home plate umpire feed"
$lines += "- Real umpire strike-zone historical model"
$lines += "- Team/player platoon splits vs LHP/RHP source"
$lines += "- True xFIP / advanced starter stats source"
$lines += "- True bullpen leverage index / pitches / availability"
$lines += ""
$lines += "TRAINING POLICY"
$lines += $train

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    umpireConnectedRows=$umpConnected
    pitcherConnectedRows=$pitchConnected
    platoonConnectedRows=$platoonConnected
    bullpenRows=$bull.Count
    eliteCoreConnectedRows=$eliteCore
    fullEliteConnectedRows=$eliteFull
    eliteSendOk=$send
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
