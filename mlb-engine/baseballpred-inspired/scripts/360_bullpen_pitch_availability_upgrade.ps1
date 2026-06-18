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

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Team-Match($a, $b) {
    $na = Normalize-Name $a
    $nb = Normalize-Name $b
    if ($na -eq "" -or $nb -eq "") { return $false }
    if ($na -eq $nb) { return $true }
    if ($na.Contains($nb) -or $nb.Contains($na)) { return $true }
    $aw = @($na -split " ")
    $bw = @($nb -split " ")
    $alast = $aw[$aw.Count-1]
    $blast = $bw[$bw.Count-1]
    if ($alast -eq $blast -and $alast.Length -gt 3) { return $true }
    return $false
}

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Add-PitcherRow {
    param(
        [System.Collections.ArrayList]$Rows,
        [string]$DateKey,
        [string]$GamePk,
        [string]$TeamName,
        [string]$Side,
        [string]$PitcherId,
        [string]$PitcherName,
        [int]$Order,
        $Pitching,
        [string]$Source
    )

    if ($PitcherName -eq "") { return }

    $pitches = Get-Val $Pitching @("numberOfPitches","pitchesThrown","pitches")
    $ip = Get-Val $Pitching @("inningsPitched")
    $bf = Get-Val $Pitching @("battersFaced")

    # Real usage row if a player has pitching stats or appears in pitcher list.
    $role = if ($Order -le 1) { "STARTER_OR_OPENER" } else { "BULLPEN_USED" }

    [void]$Rows.Add([pscustomobject]@{
        Date=$DateKey
        GamePk="$GamePk"
        Team=$TeamName
        Side=$Side
        Pitcher=$PitcherName
        PitcherId="$PitcherId"
        PitcherOrder=$Order
        Role=$role
        Pitches=$pitches
        InningsPitched=$ip
        BattersFaced=$bf
        Source=$Source
        UpdatedAt=(Get-Date).ToString("o")
    })
}

function Parse-TeamPitchersFromBoxObject {
    param(
        $Box,
        [string]$DateKey,
        [string]$GamePk,
        [string]$SourceLabel
    )

    $rows = New-Object System.Collections.ArrayList

    foreach ($side in @("away","home")) {
        $teamObj = $null
        try { $teamObj = $Box.teams.$side } catch {}
        if ($null -eq $teamObj) { continue }

        $teamName = ""
        try { $teamName = "$($teamObj.team.name)" } catch {}
        if ($teamName -eq "") { $teamName = Get-Val $teamObj @("teamName","name") }

        $orderMap = @{}
        $order = 0

        # Method A: official pitcher id list if present.
        $pitcherIds = @()
        try { $pitcherIds = @($teamObj.pitchers) } catch {}
        foreach ($pid in $pitcherIds) {
            $order++
            $orderMap["$pid"] = $order
            $key = "ID$pid"
            $player = $null
            try { $player = $teamObj.players.$key } catch {}
            $name = ""
            try { $name = "$($player.person.fullName)" } catch {}
            $pitching = $null
            try { $pitching = $player.stats.pitching } catch {}
            Add-PitcherRow -Rows $rows -DateKey $DateKey -GamePk $GamePk -TeamName $teamName -Side $side -PitcherId "$pid" -PitcherName $name -Order $order -Pitching $pitching -Source "$SourceLabel pitcher-list"
        }

        # Method B: scan all players for stats.pitching. This catches boxscores where pitcher list is absent/empty.
        $players = $null
        try { $players = $teamObj.players } catch {}
        if ($null -ne $players) {
            foreach ($prop in @($players.PSObject.Properties)) {
                $player = $prop.Value
                $pid = "$($prop.Name)" -replace "^ID", ""
                $pitching = $null
                try { $pitching = $player.stats.pitching } catch {}

                if ($null -eq $pitching) { continue }

                $ip = Get-Val $pitching @("inningsPitched")
                $bf = Get-Val $pitching @("battersFaced")
                $np = Get-Val $pitching @("numberOfPitches","pitchesThrown","pitches")
                $hasPitchingLine = ($ip -ne "" -or $bf -ne "" -or $np -ne "")
                if (-not $hasPitchingLine) { continue }

                if ($orderMap.ContainsKey("$pid")) { continue }

                $order++
                $name = ""
                try { $name = "$($player.person.fullName)" } catch {}
                Add-PitcherRow -Rows $rows -DateKey $DateKey -GamePk $GamePk -TeamName $teamName -Side $side -PitcherId "$pid" -PitcherName $name -Order $order -Pitching $pitching -Source "$SourceLabel player-scan"
            }
        }
    }

    return @($rows)
}

function Get-AllPitchRowsForGame {
    param([string]$GamePk, [string]$DateKey)

    $all = @()

    # Endpoint 1: direct boxscore.
    $box = Invoke-Json "https://statsapi.mlb.com/api/v1/game/$GamePk/boxscore" 30
    if ($null -ne $box) {
        $all += @(Parse-TeamPitchersFromBoxObject -Box $box -DateKey $DateKey -GamePk $GamePk -SourceLabel "MLB StatsAPI /api/v1/game/boxscore")
    }

    # Endpoint 2: feed/live boxscore.
    if ($all.Count -eq 0) {
        $feed = Invoke-Json "https://statsapi.mlb.com/api/v1.1/game/$GamePk/feed/live" 30
        if ($null -ne $feed) {
            $liveBox = $null
            try { $liveBox = $feed.liveData.boxscore } catch {}
            if ($null -ne $liveBox) {
                $all += @(Parse-TeamPitchersFromBoxObject -Box $liveBox -DateKey $DateKey -GamePk $GamePk -SourceLabel "MLB StatsAPI feed/live boxscore")
            }
        }
    }

    return @($all)
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$plannerCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$leverageCsv = Join-Path $astro "ASTRODDS-premium-input-bullpen-leverage-availability.csv"
$outPitchCsv = Join-Path $astro "ASTRODDS-360-bullpen-pitch-usage-raw-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.json"

Write-Host ""
Write-Host "ASTRODDS 360C BULLPEN BOXSCORE PARSER FIX" -ForegroundColor Cyan
Write-Host "Uses boxscore pitcher list + scans player stats.pitching. No fake usage." -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $leverageCsv)) {
    "Team,Reliever,Role,LeverageIndex,AvailabilityStatus,Source,UpdatedAt" | Set-Content -Encoding UTF8 $leverageCsv
}

$allPitchRows = @()
$dates = @()
for ($i=0; $i -le 3; $i++) { $dates += (Get-Date).AddDays(-$i).ToString("yyyy-MM-dd") }

foreach ($date in $dates) {
    $resp = Invoke-Json "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=team" 30
    if ($null -eq $resp) { continue }

    foreach ($d in @($resp.dates)) {
        foreach ($g in @($d.games)) {
            $status = "$($g.status.detailedState)"
            if ($status -match "Final|Game Over|Completed|In Progress|Delayed|Suspended") {
                $allPitchRows += @(Get-AllPitchRowsForGame -GamePk "$($g.gamePk)" -DateKey $date)
            }
        }
    }
}

$allPitchRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outPitchCsv

$planner = Safe-Csv $plannerCsv
$currentTeams = @()
foreach ($g in $planner) {
    $game = Get-Val $g @("Game")
    if ($game -match "\s@\s") {
        $p = $game -split "\s@\s", 2
        $currentTeams += $p[0]
        $currentTeams += $p[1]
    }
}
$currentTeams = @($currentTeams | Where-Object { "$_".Trim() -ne "" } | Select-Object -Unique)

$leverage = Safe-Csv $leverageCsv
$out = @()

foreach ($teamName in $currentTeams) {
    $teamPitch = @($allPitchRows | Where-Object { Team-Match $_.Team $teamName -and $_.Role -eq "BULLPEN_USED" })
    $last1 = @($teamPitch | Where-Object { $_.Date -eq (Get-Date).ToString("yyyy-MM-dd") })
    $last3 = @($teamPitch | Where-Object {
        try { ([datetime]$_.Date) -ge (Get-Date).Date.AddDays(-3) } catch { $false }
    })

    $totalPitches3 = 0
    $pitchesKnownCount = 0
    $maxPitcherPitches3 = 0
    foreach ($r in $last3) {
        $n = Num $r.Pitches
        if ($null -ne $n) {
            $pitchesKnownCount++
            $totalPitches3 += [int]$n
            if ($n -gt $maxPitcherPitches3) { $maxPitcherPitches3 = [int]$n }
        }
    }

    $usedToday = @($last1 | Select-Object -ExpandProperty Pitcher -Unique).Count
    $usedRelievers3 = @($last3 | Select-Object -ExpandProperty Pitcher -Unique).Count

    $pitchUsageStatus = "MISSING_RECENT_BULLPEN_USAGE"
    if ($last3.Count -gt 0 -and $pitchesKnownCount -gt 0) {
        $pitchUsageStatus = "MLB_BOXSCORE_PITCH_COUNTS_CONNECTED"
    } elseif ($last3.Count -gt 0) {
        $pitchUsageStatus = "MLB_BOXSCORE_BULLPEN_USAGE_CONNECTED_NO_PITCH_COUNTS"
    }

    $stress = "UNKNOWN"
    if ($pitchUsageStatus -eq "MLB_BOXSCORE_PITCH_COUNTS_CONNECTED") {
        if ($totalPitches3 -ge 180 -or $usedToday -ge 4) { $stress = "HIGH_USAGE_STRESS_REAL_PITCHES" }
        elseif ($totalPitches3 -ge 90 -or $usedToday -ge 2) { $stress = "MEDIUM_USAGE_STRESS_REAL_PITCHES" }
        else { $stress = "LOW_USAGE_STRESS_REAL_PITCHES" }
    } elseif ($pitchUsageStatus -eq "MLB_BOXSCORE_BULLPEN_USAGE_CONNECTED_NO_PITCH_COUNTS") {
        if ($usedRelievers3 -ge 8 -or $usedToday -ge 4) { $stress = "HIGH_USAGE_STRESS_REAL_USAGE_NO_PITCH_COUNTS" }
        elseif ($usedRelievers3 -ge 4 -or $usedToday -ge 2) { $stress = "MEDIUM_USAGE_STRESS_REAL_USAGE_NO_PITCH_COUNTS" }
        else { $stress = "LOW_USAGE_STRESS_REAL_USAGE_NO_PITCH_COUNTS" }
    }

    $liRows = @($leverage | Where-Object { Team-Match (Get-Val $_ @("Team")) $teamName })
    $liStatus = if ($liRows.Count -gt 0) { "CSV_TRUE_LEVERAGE_CONNECTED" } else { "MISSING_TRUE_LEVERAGE_SOURCE" }

    $out += ,[pscustomobject]@{
        Team=$teamName
        PitchUsageStatus=$pitchUsageStatus
        BullpenStressFromRealUsage=$stress
        RelieversUsedToday=$usedToday
        RelieversUsedLast3Days=$usedRelievers3
        BullpenPitchesLast3Days=if ($pitchesKnownCount -gt 0) { $totalPitches3 } else { "" }
        PitchCountsKnownRows=$pitchesKnownCount
        RawBullpenUsageRows=$last3.Count
        MaxSingleRelieverPitchesLast3Days=if ($pitchesKnownCount -gt 0) { $maxPitcherPitches3 } else { "" }
        TrueLeverageStatus=$liStatus
        LeverageCsv=$leverageCsv
        RawPitchUsageCsv=$outPitchCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$usageConnected = @($out | Where-Object { $_.PitchUsageStatus -match "CONNECTED" }).Count
$pitchCountsConnected = @($out | Where-Object { $_.PitchUsageStatus -eq "MLB_BOXSCORE_PITCH_COUNTS_CONNECTED" }).Count
$liConnected = @($out | Where-Object { $_.TrueLeverageStatus -eq "CSV_TRUE_LEVERAGE_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 360C BULLPEN BOXSCORE PARSER FIX"
$lines += ""
$lines += "Teams: $($out.Count)"
$lines += "Real bullpen usage connected teams: $usageConnected"
$lines += "Real pitch counts connected teams: $pitchCountsConnected"
$lines += "True leverage CSV connected teams: $liConnected"
$lines += "Raw pitch usage rows: $($allPitchRows.Count)"
$lines += "Raw pitch usage file: $outPitchCsv"
$lines += "Leverage CSV template: $leverageCsv"
$lines += ""
$lines += "RULE"
$lines += "- Usage comes from MLB boxscore pitcher lists and player stats.pitching."
$lines += "- Pitch-count stress only uses real pitch-count fields when present."
$lines += "- True leverage index still requires CSV/export; no fake LI."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Team) | usage=$($r.PitchUsageStatus) | stress=$($r.BullpenStressFromRealUsage) | leverage=$($r.TrueLeverageStatus) | rawRows=$($r.RawBullpenUsageRows)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    teams=$out.Count
    realBullpenUsageConnectedTeams=$usageConnected
    realPitchCountsConnectedTeams=$pitchCountsConnected
    trueLeverageConnectedTeams=$liConnected
    rawPitchUsageRows=$allPitchRows.Count
    outputCsv=$outCsv
    rawPitchUsageCsv=$outPitchCsv
    leverageCsv=$leverageCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
