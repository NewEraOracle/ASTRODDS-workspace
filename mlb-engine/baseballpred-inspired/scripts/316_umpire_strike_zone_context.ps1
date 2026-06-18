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
$manualCsv = Join-Path $astro "ASTRODDS-umpire-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-umpire-strike-zone-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-316-umpire-strike-zone-context-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-316-umpire-strike-zone-context-latest.json"

Write-Host ""
Write-Host "ASTRODDS 316 UMPIRE / STRIKE ZONE CONTEXT" -ForegroundColor Cyan
Write-Host "No fake umpire data. Uses optional ASTRODDS-umpire-source-latest.csv if present." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv
$manual = Safe-Csv $manualCsv
$out = @()

foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $u = Find-By-Game $manual $game

    $status = "UMPIRE_SOURCE_MISSING"
    $ump = ""
    $zone = "unknown"
    $kBoost = ""
    $bbBoost = ""
    $ouBias = "unknown"
    $officialUse = "REVIEW_CONTEXT_ONLY"

    if ($null -ne $u) {
        $ump = Get-Val $u @("HomePlateUmpire","Umpire","Name")
        $zone = Get-Val $u @("ZoneBias","StrikeZoneBias")
        $kBoost = Get-Val $u @("KBoost","StrikeoutBoost")
        $bbBoost = Get-Val $u @("WalkBoost","BBBoost")
        $ouBias = Get-Val $u @("OverUnderBias","RunEnvironmentBias")
        $status = "UMPIRE_SOURCE_CONNECTED"
        $officialUse = "CONNECTED_CONTEXT"
    }

    $out += ,[pscustomobject]@{
        Source = if ($null -ne $u) { "USER_OR_EXTERNAL_UMPIRE_SOURCE" } else { "NO_PUBLIC_UMPIRE_SOURCE_CONNECTED" }
        Game = $game
        GamePk = Get-Val $g @("GamePk")
        MlbStatus = Get-Val $g @("MlbStatus")
        HomePlateUmpire = $ump
        ZoneBias = $zone
        KBoost = $kBoost
        WalkBoost = $bbBoost
        OverUnderBias = $ouBias
        UmpireContextStatus = $status
        OfficialUse = $officialUse
        Note = "Do not invent umpire. Add ASTRODDS-umpire-source-latest.csv to connect this premium factor."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$connected = @($out | Where-Object { $_.UmpireContextStatus -eq "UMPIRE_SOURCE_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 316 UMPIRE / STRIKE ZONE CONTEXT"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Connected umpire rows: $connected"
$lines += "Missing umpire rows: $($out.Count - $connected)"
$lines += ""
$lines += "OPTIONAL SOURCE FORMAT"
$lines += "Create: .astrodds\ASTRODDS-umpire-source-latest.csv"
$lines += "Columns: Game,HomePlateUmpire,ZoneBias,KBoost,WalkBoost,OverUnderBias"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.UmpireContextStatus) | $($r.Game) | umpire=$($r.HomePlateUmpire) | zone=$($r.ZoneBias)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
