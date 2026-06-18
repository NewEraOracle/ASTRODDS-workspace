$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"

$outJson = Join-Path $astro "ASTRODDS-scan-coverage-and-pick-reasons-latest.json"
$outTxt  = Join-Path $astro "ASTRODDS-scan-coverage-and-pick-reasons-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 213 SCAN COVERAGE + PICK REASONS AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) {
        Write-Host "WARNING missing file: $path" -ForegroundColor Yellow
        return $null
    }

    try {
        return Get-Content $path -Raw | ConvertFrom-Json
    } catch {
        Write-Host "WARNING invalid JSON: $path" -ForegroundColor Yellow
        Write-Host $_.Exception.Message
        return $null
    }
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $n = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$n)) {
        return $n
    }
    return $null
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", [System.Globalization.CultureInfo]::InvariantCulture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", [System.Globalization.CultureInfo]::InvariantCulture) + "¢"
}

function FirstValue($items, $prop) {
    foreach ($x in @($items)) {
        if ($null -ne $x.$prop -and "$($x.$prop)".Trim() -ne "") {
            return "$($x.$prop)"
        }
    }
    return ""
}

function Get-ContextRows($boardRow, $name) {
    if ($null -eq $boardRow.contexts) { return @() }
    if ($null -eq $boardRow.contexts.$name) { return @() }
    return @($boardRow.contexts.$name)
}

$officialRows = @()
if (Test-Path $lockedOfficial) {
    $officialRows = @(Read-JsonSafe $lockedOfficial)
}

$ranker = Read-JsonSafe $rankerFile
$public = Read-JsonSafe $publicBoard

$gameBoard = @()
if ($null -ne $ranker -and $ranker.gameBoard) {
    $gameBoard = @($ranker.gameBoard)
}

$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @($public.aPicks)
}

$publicNoBets = @()
if ($null -ne $public -and $public.noBets) {
    $publicNoBets = @($public.noBets)
}
if ($null -ne $public -and $public.NO_BET) {
    $publicNoBets += @($public.NO_BET)
}

$csvRows = @()
if (Test-Path $fullSlateCsv) {
    try {
        $csvRows = @(Import-Csv $fullSlateCsv)
    } catch {
        Write-Host "WARNING cannot read full slate CSV." -ForegroundColor Yellow
    }
}

$allGames = New-Object System.Collections.Generic.HashSet[string]

foreach ($r in $gameBoard) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $publicAPicks) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $publicNoBets) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $csvRows) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}

$officialGames = New-Object System.Collections.Generic.HashSet[string]
foreach ($r in $officialRows) {
    if ($r.Game) { [void]$officialGames.Add("$($r.Game)") }
}

$paperCount = @($gameBoard | Where-Object { "$($_.status)" -match "PAPER|REVIEW|A_PAPER" }).Count
$noBetCount = $publicNoBets.Count

$reasonRows = @()

foreach ($o in $officialRows) {
    $game = "$($o.Game)"
    $pick = "$($o.Pick)"

    $match = $gameBoard | Where-Object {
        "$($_.game)" -eq $game -and "$($_.pick)" -eq $pick
    } | Select-Object -First 1

    if ($null -eq $match) {
        $match = $gameBoard | Where-Object {
            "$($_.game)" -eq $game
        } | Select-Object -First 1
    }

    $pitcherRows = Get-ContextRows $match "pitcher"
    $bullpenRows = Get-ContextRows $match "bullpen"
    $injuryRows  = Get-ContextRows $match "injury"
    $lineupRows  = Get-ContextRows $match "lineup"
    $bpenWhipRows = Get-ContextRows $match "exactBpenWhip35"

    $awayPitcher = FirstValue $pitcherRows "awayProbablePitcher"
    $homePitcher = FirstValue $pitcherRows "homeProbablePitcher"

    $awayEra = FirstValue $pitcherRows "awayPitcher_era"
    $homeEra = FirstValue $pitcherRows "homePitcher_era"
    $awayWhip = FirstValue $pitcherRows "awayPitcher_whip"
    $homeWhip = FirstValue $pitcherRows "homePitcher_whip"

    $awayBullpen = FirstValue $bullpenRows "awayBullpenFatigueLabel"
    $homeBullpen = FirstValue $bullpenRows "homeBullpenFatigueLabel"
    $awayBpenFlags = FirstValue $bullpenRows "awayBullpenFlags"
    $homeBpenFlags = FirstValue $bullpenRows "homeBullpenFlags"

    $pickedInjuryRisk = FirstValue $injuryRows "pickedTeamInjuryRisk"
    $opponentInjuryRisk = FirstValue $injuryRows "opponentInjuryRisk"
    $injuryDetails = FirstValue $injuryRows "pickedTeamInjuryDetails"

    $awayLineup = FirstValue $lineupRows "awayLineupStatus"
    $homeLineup = FirstValue $lineupRows "homeLineupStatus"
    $venue = FirstValue $lineupRows "venue"

    $why = New-Object System.Collections.Generic.List[string]

    $why.Add("Market value: entry " + (Cents $o.Price) + ", model " + (Pct $o.ModelProbability) + ", edge +" + (Pct $o.EdgePct) + ".")

    if ($awayPitcher -or $homePitcher) {
        $why.Add("Pitchers: $awayPitcher vs $homePitcher. ERA: $awayEra vs $homeEra. WHIP: $awayWhip vs $homeWhip.")
    }

    if ($awayBullpen -or $homeBullpen) {
        $why.Add("Bullpen fatigue: away $awayBullpen, home $homeBullpen. Flags: away [$awayBpenFlags], home [$homeBpenFlags].")
    }

    if ($pickedInjuryRisk -or $opponentInjuryRisk) {
        $why.Add("Injuries: picked team risk $pickedInjuryRisk, opponent risk $opponentInjuryRisk.")
    }

    if ($injuryDetails -and $injuryDetails -notmatch "No recent") {
        $why.Add("Injury detail: $injuryDetails")
    }

    if ($awayLineup -or $homeLineup) {
        $why.Add("Lineups: away $awayLineup, home $homeLineup. This matters because missing lineups add uncertainty.")
    }

    if ($venue) {
        $why.Add("Venue: $venue.")
    }

    $reasonRows += [pscustomobject]@{
        Rank = $o.Rank
        Pick = $pick
        Game = $game
        Price = $o.Price
        ModelProbability = $o.ModelProbability
        EdgePct = $o.EdgePct
        RiskLevel = $o.RiskLevel
        WhyImportant = $why -join " "
    }
}

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("ASTRODDS 213 SCAN COVERAGE + PICK REASONS AUDIT")
$lines.Add("")
$lines.Add("COVERAGE")
$lines.Add("Unique games found across available sources: $($allGames.Count)")
$lines.Add("Official games locked: $($officialRows.Count)")
$lines.Add("Paper/review rows found: $paperCount")
$lines.Add("NO_BET rows found: $noBetCount")
$lines.Add("")

if ($allGames.Count -le 3) {
    $lines.Add("WARNING: Coverage looks low. This may mean the slate source did not load all games, or only official rows are being read.")
} else {
    $lines.Add("Coverage check: Multiple games were found across the available slate/context files.")
}

$lines.Add("")
$lines.Add("WHY THESE OFFICIAL PICKS")
$lines.Add("")

foreach ($r in $reasonRows) {
    $lines.Add("#$($r.Rank) $($r.Pick)")
    $lines.Add("Game: $($r.Game)")
    $lines.Add("Value: " + (Cents $r.Price) + " | Model: " + (Pct $r.ModelProbability) + " | Edge: +" + (Pct $r.EdgePct))
    $lines.Add("Why: $($r.WhyImportant)")
    $lines.Add("")
}

$lines.Add("IMPORTANT")
$lines.Add("These reasons explain why the model found value. They do NOT guarantee a win.")
$lines.Add("If lineups are missing, risk stays higher until confirmed.")

$result = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    uniqueGamesFound = $allGames.Count
    officialCount = $officialRows.Count
    paperReviewCount = $paperCount
    noBetCount = $noBetCount
    officialReasons = $reasonRows
    sourceFiles = @(
        $lockedOfficial,
        $rankerFile,
        $publicBoard,
        $fullSlateCsv
    )
}

$result | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
