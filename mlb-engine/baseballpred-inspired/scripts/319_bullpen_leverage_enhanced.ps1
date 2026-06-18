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
$scheduleJson = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.json"
$outCsv = Join-Path $astro "ASTRODDS-bullpen-leverage-enhanced-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-319-bullpen-leverage-enhanced-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-319-bullpen-leverage-enhanced-latest.json"

Write-Host ""
Write-Host "ASTRODDS 319 ENHANCED BULLPEN LEVERAGE PROXY" -ForegroundColor Cyan
Write-Host "Uses recent MLB games. Close-game + reliever usage proxy; does not fake leverage index." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv
$today = Get-Date
$teams = @{}
foreach ($g in $schedule) {
    foreach ($t in @((Get-Val $g @("AwayTeam")), (Get-Val $g @("HomeTeam")))) {
        if ($t -ne "" -and -not $teams.ContainsKey($t)) {
            $teams[$t] = [pscustomobject]@{ Team=$t; Games3=0; Games7=0; CloseGames3=0; CloseGames7=0; Pitchers3=0; Pitchers7=0; ReliefStressScore=0 }
        }
    }
}

for ($i=1; $i -le 7; $i++) {
    $date = $today.AddDays(-$i).ToString("yyyy-MM-dd")
    $sched = Invoke-Json "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date" 25
    if ($null -eq $sched) { continue }

    foreach ($d in @($sched.dates)) {
        foreach ($gm in @($d.games)) {
            $away = "$($gm.teams.away.team.name)"
            $home = "$($gm.teams.home.team.name)"
            if (-not $teams.ContainsKey($away) -and -not $teams.ContainsKey($home)) { continue }

            $gamePk = "$($gm.gamePk)"
            $feed = Invoke-Json "https://statsapi.mlb.com/api/v1.1/game/$gamePk/feed/live" 25
            $awayPitchers = 0
            $homePitchers = 0
            try { $awayPitchers = @($feed.liveData.boxscore.teams.away.pitchers).Count } catch {}
            try { $homePitchers = @($feed.liveData.boxscore.teams.home.pitchers).Count } catch {}

            $awayScore = Num "$($gm.teams.away.score)"
            $homeScore = Num "$($gm.teams.home.score)"
            $close = $false
            if ($null -ne $awayScore -and $null -ne $homeScore) {
                if ([math]::Abs($awayScore - $homeScore) -le 3) { $close = $true }
            }

            foreach ($side in @(
                @{Team=$away; Pitchers=$awayPitchers},
                @{Team=$home; Pitchers=$homePitchers}
            )) {
                $team = $side.Team
                if (-not $teams.ContainsKey($team)) { continue }
                $obj = $teams[$team]
                $obj.Games7 += 1
                $obj.Pitchers7 += [int]$side.Pitchers
                if ($close) { $obj.CloseGames7 += 1 }
                if ($i -le 3) {
                    $obj.Games3 += 1
                    $obj.Pitchers3 += [int]$side.Pitchers
                    if ($close) { $obj.CloseGames3 += 1 }
                }
            }
        }
    }
}

foreach ($k in @($teams.Keys)) {
    $t = $teams[$k]
    $score = 0
    $score += $t.CloseGames3 * 2
    $score += $t.CloseGames7 * 1
    $score += [math]::Max(0, $t.Pitchers3 - ($t.Games3 * 3))
    $score += [math]::Max(0, ($t.Pitchers7 - ($t.Games7 * 3)) * 0.5)
    $t.ReliefStressScore = [math]::Round($score, 1)
}

function StressLevel($score) {
    if ($score -ge 10) { return "high" }
    if ($score -ge 6) { return "medium" }
    if ($score -gt 0) { return "low" }
    return "normal"
}

$out = @()
foreach ($g in $schedule) {
    $away = Get-Val $g @("AwayTeam")
    $home = Get-Val $g @("HomeTeam")
    $a = $teams[$away]
    $h = $teams[$home]

    $out += ,[pscustomobject]@{
        Source = "MLB_STATSAPI_BULLPEN_LEVERAGE_PROXY"
        Game = Get-Val $g @("Game")
        GamePk = Get-Val $g @("GamePk")
        AwayTeam = $away
        HomeTeam = $home
        AwayCloseGames3 = $a.CloseGames3
        AwayCloseGames7 = $a.CloseGames7
        AwayPitchersUsed3 = $a.Pitchers3
        AwayPitchersUsed7 = $a.Pitchers7
        AwayReliefStressScore = $a.ReliefStressScore
        AwayReliefStressLevel = StressLevel $a.ReliefStressScore
        HomeCloseGames3 = $h.CloseGames3
        HomeCloseGames7 = $h.CloseGames7
        HomePitchersUsed3 = $h.Pitchers3
        HomePitchersUsed7 = $h.Pitchers7
        HomeReliefStressScore = $h.ReliefStressScore
        HomeReliefStressLevel = StressLevel $h.ReliefStressScore
        Note = "Proxy: close games + pitcher usage. True leverage index requires premium/event-level source."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$lines = @()
$lines += "ASTRODDS 319 ENHANCED BULLPEN LEVERAGE PROXY"
$lines += ""
$lines += "Rows: $($out.Count)"
foreach ($r in $out) {
    $lines += "- $($r.Game) | awayStress=$($r.AwayReliefStressLevel) score=$($r.AwayReliefStressScore) | homeStress=$($r.HomeReliefStressLevel) score=$($r.HomeReliefStressScore)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
