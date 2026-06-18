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

$scheduleJson = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.json"
$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-starter-advanced-pitcher-metrics-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-317-starter-advanced-pitcher-metrics-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-317-starter-advanced-pitcher-metrics-latest.json"

Write-Host ""
Write-Host "ASTRODDS 317 STARTER ADVANCED PITCHER METRICS" -ForegroundColor Cyan
Write-Host "Fetches MLB StatsAPI season pitching stats and calculates FIP/K-BB proxy." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv
$probables = @{}

try {
    $raw = Get-Content $scheduleJson -Raw | ConvertFrom-Json
    foreach ($d in @($raw.dates)) {
        foreach ($g in @($d.games)) {
            $gamePk = "$($g.gamePk)"
            $game = "$($g.teams.away.team.name) @ $($g.teams.home.team.name)"
            $awayPid = ""
            $homePid = ""
            $awayName = ""
            $homeName = ""
            try { $awayPid = "$($g.teams.away.probablePitcher.id)"; $awayName = "$($g.teams.away.probablePitcher.fullName)" } catch {}
            try { $homePid = "$($g.teams.home.probablePitcher.id)"; $homeName = "$($g.teams.home.probablePitcher.fullName)" } catch {}
            $probables[$gamePk] = [pscustomobject]@{
                Game = $game
                GamePk = $gamePk
                AwayPitcherId = $awayPid
                AwayPitcher = $awayName
                HomePitcherId = $homePid
                HomePitcher = $homeName
            }
        }
    }
} catch {}

function Get-PitcherMetric($id, $name) {
    if ($id -eq "") {
        return [pscustomobject]@{
            PitcherId=""; Pitcher=$name; PitchHand=""; ERA=""; WHIP=""; InningsPitched=""; Strikeouts=""; Walks=""; HomeRuns=""; BattersFaced="";
            FIPProxy=""; KMinusBBPctProxy=""; Status="PITCHER_ID_MISSING"
        }
    }

    $person = Invoke-Json "https://statsapi.mlb.com/api/v1/people/$id" 20
    $stats = Invoke-Json "https://statsapi.mlb.com/api/v1/people/$id/stats?stats=season&group=pitching" 20

    $hand = ""
    try { $hand = "$($person.people[0].pitchHand.code)" } catch {}
    $fullName = $name
    try { if ("$($person.people[0].fullName)" -ne "") { $fullName = "$($person.people[0].fullName)" } } catch {}

    $s = $null
    try { $s = $stats.stats[0].splits[0].stat } catch {}

    if ($null -eq $s) {
        return [pscustomobject]@{
            PitcherId=$id; Pitcher=$fullName; PitchHand=$hand; ERA=""; WHIP=""; InningsPitched=""; Strikeouts=""; Walks=""; HomeRuns=""; BattersFaced="";
            FIPProxy=""; KMinusBBPctProxy=""; Status="PITCHING_STATS_MISSING"
        }
    }

    $ipText = "$($s.inningsPitched)"
    $ip = Ip-To-Decimal $ipText
    $k = Num "$($s.strikeOuts)"
    $bb = Num "$($s.baseOnBalls)"
    $hr = Num "$($s.homeRuns)"
    $bf = Num "$($s.battersFaced)"

    $fip = ""
    if ($null -ne $ip -and $ip -gt 0 -and $null -ne $k -and $null -ne $bb -and $null -ne $hr) {
        # FIP proxy. Real league FIP constant changes by season; 3.10 used only as a stable baseline.
        $fip = [math]::Round(((13*$hr + 3*$bb - 2*$k) / $ip) + 3.10, 2)
    }

    $kbb = ""
    if ($null -ne $bf -and $bf -gt 0 -and $null -ne $k -and $null -ne $bb) {
        $kbb = ([math]::Round((($k - $bb) / $bf) * 100.0, 1)).ToString() + "%"
    }

    return [pscustomobject]@{
        PitcherId=$id
        Pitcher=$fullName
        PitchHand=$hand
        ERA="$($s.era)"
        WHIP="$($s.whip)"
        InningsPitched=$ipText
        Strikeouts="$($s.strikeOuts)"
        Walks="$($s.baseOnBalls)"
        HomeRuns="$($s.homeRuns)"
        BattersFaced="$($s.battersFaced)"
        FIPProxy="$fip"
        KMinusBBPctProxy="$kbb"
        Status="CONNECTED_STATSAPI"
    }
}

$out = @()
foreach ($g in $schedule) {
    $gamePk = Get-Val $g @("GamePk")
    $game = Get-Val $g @("Game")
    $p = $probables[$gamePk]

    $awayMetric = $null
    $homeMetric = $null

    if ($null -ne $p) {
        $awayMetric = Get-PitcherMetric "$($p.AwayPitcherId)" "$($p.AwayPitcher)"
        $homeMetric = Get-PitcherMetric "$($p.HomePitcherId)" "$($p.HomePitcher)"
    } else {
        $awayMetric = Get-PitcherMetric "" ""
        $homeMetric = Get-PitcherMetric "" ""
    }

    $out += ,[pscustomobject]@{
        Source = "MLB_STATSAPI_SEASON_PITCHING_ADVANCED_PROXY"
        Game = $game
        GamePk = $gamePk
        AwayTeam = Get-Val $g @("AwayTeam")
        HomeTeam = Get-Val $g @("HomeTeam")
        AwayStarter = $awayMetric.Pitcher
        AwayStarterId = $awayMetric.PitcherId
        AwayStarterHand = $awayMetric.PitchHand
        AwayERA = $awayMetric.ERA
        AwayWHIP = $awayMetric.WHIP
        AwayFIPProxy = $awayMetric.FIPProxy
        AwayKMinusBBPctProxy = $awayMetric.KMinusBBPctProxy
        AwayPitcherStatus = $awayMetric.Status
        HomeStarter = $homeMetric.Pitcher
        HomeStarterId = $homeMetric.PitcherId
        HomeStarterHand = $homeMetric.PitchHand
        HomeERA = $homeMetric.ERA
        HomeWHIP = $homeMetric.WHIP
        HomeFIPProxy = $homeMetric.FIPProxy
        HomeKMinusBBPctProxy = $homeMetric.KMinusBBPctProxy
        HomePitcherStatus = $homeMetric.Status
        Note = "FIPProxy uses fixed constant 3.10; xFIP requires batted-ball/FB source and is not faked."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$connected = @($out | Where-Object { $_.AwayPitcherStatus -eq "CONNECTED_STATSAPI" -or $_.HomePitcherStatus -eq "CONNECTED_STATSAPI" }).Count

$lines = @()
$lines += "ASTRODDS 317 STARTER ADVANCED PITCHER METRICS"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Rows with at least one connected starter stats: $connected"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Game)"
    $lines += "  Away: $($r.AwayStarter) $($r.AwayStarterHand) | ERA=$($r.AwayERA) WHIP=$($r.AwayWHIP) FIPp=$($r.AwayFIPProxy) K-BB=$($r.AwayKMinusBBPctProxy) | $($r.AwayPitcherStatus)"
    $lines += "  Home: $($r.HomeStarter) $($r.HomeStarterHand) | ERA=$($r.HomeERA) WHIP=$($r.HomeWHIP) FIPp=$($r.HomeFIPProxy) K-BB=$($r.HomeKMinusBBPctProxy) | $($r.HomePitcherStatus)"
}

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
