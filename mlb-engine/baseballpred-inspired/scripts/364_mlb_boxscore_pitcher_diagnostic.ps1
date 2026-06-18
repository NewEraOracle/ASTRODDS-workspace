$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-364-mlb-boxscore-pitcher-diagnostic-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-364-mlb-boxscore-pitcher-diagnostic-latest.json"

Write-Host ""
Write-Host "ASTRODDS 364 MLB BOXSCORE PITCHER DIAGNOSTIC" -ForegroundColor Cyan
Write-Host ""

$date = (Get-Date).ToString("yyyy-MM-dd")
$schedule = Invoke-Json "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=team" 30
$rows = @()

foreach ($d in @($schedule.dates)) {
    foreach ($g in @($d.games)) {
        $gamePk = "$($g.gamePk)"
        $status = "$($g.status.detailedState)"
        $away = "$($g.teams.away.team.name)"
        $home = "$($g.teams.home.team.name)"

        $box = Invoke-Json "https://statsapi.mlb.com/api/v1/game/$gamePk/boxscore" 30
        $feed = Invoke-Json "https://statsapi.mlb.com/api/v1.1/game/$gamePk/feed/live" 30

        $boxAwayPitchers = 0
        $boxHomePitchers = 0
        $boxAwayPlayers = 0
        $boxHomePlayers = 0
        $feedAwayPitchers = 0
        $feedHomePitchers = 0
        $feedAwayPlayers = 0
        $feedHomePlayers = 0

        try { $boxAwayPitchers = @($box.teams.away.pitchers).Count } catch {}
        try { $boxHomePitchers = @($box.teams.home.pitchers).Count } catch {}
        try { $boxAwayPlayers = @($box.teams.away.players.PSObject.Properties).Count } catch {}
        try { $boxHomePlayers = @($box.teams.home.players.PSObject.Properties).Count } catch {}

        try { $feedAwayPitchers = @($feed.liveData.boxscore.teams.away.pitchers).Count } catch {}
        try { $feedHomePitchers = @($feed.liveData.boxscore.teams.home.pitchers).Count } catch {}
        try { $feedAwayPlayers = @($feed.liveData.boxscore.teams.away.players.PSObject.Properties).Count } catch {}
        try { $feedHomePlayers = @($feed.liveData.boxscore.teams.home.players.PSObject.Properties).Count } catch {}

        $rows += ,[pscustomobject]@{
            GamePk=$gamePk
            Game="$away @ $home"
            Status=$status
            BoxscoreLoaded=($null -ne $box)
            FeedLoaded=($null -ne $feed)
            BoxAwayPitchers=$boxAwayPitchers
            BoxHomePitchers=$boxHomePitchers
            BoxAwayPlayers=$boxAwayPlayers
            BoxHomePlayers=$boxHomePlayers
            FeedAwayPitchers=$feedAwayPitchers
            FeedHomePitchers=$feedHomePitchers
            FeedAwayPlayers=$feedAwayPlayers
            FeedHomePlayers=$feedHomePlayers
        }
    }
}

$lines = @()
$lines += "ASTRODDS 364 MLB BOXSCORE PITCHER DIAGNOSTIC"
$lines += ""
$lines += "Date: $date"
$lines += "Games checked: $($rows.Count)"
$lines += ""
foreach ($r in $rows) {
    $lines += "- $($r.Game) | $($r.Status) | boxLoaded=$($r.BoxscoreLoaded) feedLoaded=$($r.FeedLoaded) | boxPitch=$($r.BoxAwayPitchers)/$($r.BoxHomePitchers) boxPlayers=$($r.BoxAwayPlayers)/$($r.BoxHomePlayers) | feedPitch=$($r.FeedAwayPitchers)/$($r.FeedHomePitchers) feedPlayers=$($r.FeedAwayPlayers)/$($r.FeedHomePlayers)"
}

$rows | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
