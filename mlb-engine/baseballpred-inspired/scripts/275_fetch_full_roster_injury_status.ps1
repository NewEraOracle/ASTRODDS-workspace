$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$scheduleJson = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.json"
$outCsv = Join-Path $astro "ASTRODDS-full-roster-injury-status-latest.csv"
$outContext = Join-Path $astro "ASTRODDS-free-injury-context-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-275-full-roster-injury-status-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-275-full-roster-injury-status-latest.json"

Write-Host ""
Write-Host "ASTRODDS 275 FULL ROSTER INJURY STATUS" -ForegroundColor Cyan
Write-Host "Source: MLB StatsAPI fullRoster + transactions proxy." -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 25 | Set-Content -Encoding UTF8 $path
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

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

$schedule = Safe-Csv $scheduleCsv
$teamIds = @{}

try {
    $raw = Get-Content $scheduleJson -Raw | ConvertFrom-Json
    foreach ($d in @($raw.dates)) {
        foreach ($g in @($d.games)) {
            $teamIds["$($g.teams.away.team.name)"] = "$($g.teams.away.team.id)"
            $teamIds["$($g.teams.home.team.name)"] = "$($g.teams.home.team.id)"
        }
    }
} catch {}

$teamInjury = @{}
$allRosterRows = @()

foreach ($teamName in $teamIds.Keys) {
    $teamId = $teamIds[$teamName]
    $url = "https://statsapi.mlb.com/api/v1/teams/$teamId/roster?rosterType=fullRoster&hydrate=person"
    $roster = Invoke-Json $url 25

    $injured = @()
    if ($null -ne $roster -and $roster.roster) {
        foreach ($p in @($roster.roster)) {
            $name = "$($p.person.fullName)"
            $statusCode = ""
            $statusDesc = ""
            try { $statusCode = "$($p.status.code)" } catch {}
            try { $statusDesc = "$($p.status.description)" } catch {}
            $pos = ""
            try { $pos = "$($p.position.abbreviation)" } catch {}

            $isInjured = $false
            if ($statusCode -match "D|IL|INJ|60|10|15" -or $statusDesc -match "injured|day|IL|list") { $isInjured = $true }
            if ($isInjured) { $injured += "$name ($pos, $statusCode $statusDesc)" }

            $allRosterRows += ,[pscustomobject]@{
                Source = "MLB_STATSAPI_FULL_ROSTER"
                Team = $teamName
                TeamId = $teamId
                Player = $name
                Position = $pos
                StatusCode = $statusCode
                StatusDescription = $statusDesc
                IsInjuryOrILSignal = $isInjured
                SourceUrl = $url
                FetchedAt = (Get-Date).ToString("o")
            }
        }
    }

    $risk = "none"
    if ($injured.Count -ge 8) { $risk = "high" }
    elseif ($injured.Count -ge 3) { $risk = "medium" }
    elseif ($injured.Count -gt 0) { $risk = "low" }

    $teamInjury[$teamName] = [pscustomobject]@{
        Team = $teamName
        InjuryRisk = $risk
        InjuredCount = $injured.Count
        InjuryDetails = (($injured | Select-Object -First 10) -join " || ")
    }
}

$contextRows = @()
foreach ($g in $schedule) {
    $awayTeamName = Get-Val $g @("AwayTeam")
    $homeTeamName = Get-Val $g @("HomeTeam")
    $a = $teamInjury[$awayTeamName]
    $h = $teamInjury[$homeTeamName]

    $contextRows += ,[pscustomobject]@{
        Source = "MLB_STATSAPI_FULL_ROSTER_INJURY_PROXY"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $g @("GamePk")
        Game = Get-Val $g @("Game")
        AwayTeam = $awayTeamName
        HomeTeam = $homeTeamName
        AwayInjuryRisk = if ($null -ne $a) { $a.InjuryRisk } else { "unknown" }
        HomeInjuryRisk = if ($null -ne $h) { $h.InjuryRisk } else { "unknown" }
        AwayInjuredCount = if ($null -ne $a) { $a.InjuredCount } else { "" }
        HomeInjuredCount = if ($null -ne $h) { $h.InjuredCount } else { "" }
        AwayInjuryDetail = if ($null -ne $a) { $a.InjuryDetails } else { "" }
        HomeInjuryDetail = if ($null -ne $h) { $h.InjuryDetails } else { "" }
        FetchedAt = (Get-Date).ToString("o")
    }
}

$allRosterRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$contextRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outContext
Write-Json @($teamInjury.Values) $outJson

$lines = @()
$lines += "ASTRODDS 275 FULL ROSTER INJURY STATUS"
$lines += ""
$lines += "Teams checked: $($teamIds.Count)"
$lines += "Roster rows: $($allRosterRows.Count)"
$lines += "Context rows: $($contextRows.Count)"
$lines += ""
foreach ($r in ($contextRows | Select-Object -First 12)) {
    $lines += "- $($r.Game) | awayRisk=$($r.AwayInjuryRisk) ($($r.AwayInjuredCount)) | homeRisk=$($r.HomeInjuryRisk) ($($r.HomeInjuredCount))"
}
$lines += ""
$lines += "Output context: $outContext"
$lines += "Output roster: $outCsv"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
