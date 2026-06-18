$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"

$outJson = Join-Path $astro "ASTRODDS-scan-coverage-and-pick-reasons-fixed-latest.json"
$outTxt  = Join-Path $astro "ASTRODDS-scan-coverage-and-pick-reasons-fixed-latest.txt"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 213B FIXED SCAN COVERAGE + PICK REASONS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) {
        Write-Host "WARNING missing file: $path" -ForegroundColor Yellow
        return $null
    }

    try {
        return (Get-Content $path -Raw | ConvertFrom-Json)
    } catch {
        Write-Host "WARNING invalid JSON: $path" -ForegroundColor Yellow
        Write-Host $_.Exception.Message
        return $null
    }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }

    if ($data -is [System.Array]) {
        return @($data)
    }

    $props = @($data.PSObject.Properties)
    $arrayProps = @($props | Where-Object {
        $_.Value -is [System.Array] -or $_.Value -is [System.Collections.IEnumerable] -and !($_.Value -is [string])
    })

    if ($arrayProps.Count -gt 0) {
        $max = 0

        foreach ($p in $arrayProps) {
            $count = @($p.Value).Count
            if ($count -gt $max) { $max = $count }
        }

        if ($max -gt 1) {
            $rows = @()

            for ($i = 0; $i -lt $max; $i++) {
                $h = [ordered]@{}

                foreach ($p in $props) {
                    $v = $p.Value

                    if (($v -is [System.Array]) -or ($v -is [System.Collections.IEnumerable] -and !($v -is [string]))) {
                        $arr = @($v)
                        if ($i -lt $arr.Count) {
                            $h[$p.Name] = $arr[$i]
                        } else {
                            $h[$p.Name] = $null
                        }
                    } else {
                        $h[$p.Name] = $v
                    }
                }

                $rows += [pscustomobject]$h
            }

            return @($rows)
        }
    }

    return @($data)
}

function Num($v) {
    if ($null -eq $v) { return $null }

    $s = "$v".Trim()
    if ($s -eq "") { return $null }

    $n = 0.0

    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }

    return $null
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "¢"
}

function FirstValue($items, $prop) {
    foreach ($x in @($items)) {
        if ($null -ne $x -and $null -ne $x.$prop -and "$($x.$prop)".Trim() -ne "") {
            return "$($x.$prop)"
        }
    }
    return ""
}

function Get-ContextRows($boardRow, $name) {
    if ($null -eq $boardRow) { return @() }
    if ($null -eq $boardRow.contexts) { return @() }
    if ($null -eq $boardRow.contexts.$name) { return @() }

    return @(Normalize-Rows $boardRow.contexts.$name)
}

$officialRaw = Read-JsonSafe $lockedOfficial
$officialRows = @(Normalize-Rows $officialRaw)

$ranker = Read-JsonSafe $rankerFile
$public = Read-JsonSafe $publicBoard

$gameBoard = @()
if ($null -ne $ranker -and $ranker.gameBoard) {
    $gameBoard = @(Normalize-Rows $ranker.gameBoard)
}

$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$publicNoBets = @()
if ($null -ne $public -and $public.noBets) {
    $publicNoBets += @(Normalize-Rows $public.noBets)
}
if ($null -ne $public -and $public.NO_BET) {
    $publicNoBets += @(Normalize-Rows $public.NO_BET)
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

$paperCount = @($gameBoard | Where-Object { "$($_.status)" -match "PAPER|REVIEW|A_PAPER" }).Count
$noBetCount = $publicNoBets.Count

$reasonRows = @()

foreach ($o in $officialRows) {
    $game = "$($o.Game)".Trim()
    $pick = "$($o.Pick)".Trim()

    if ($game -eq "" -or $pick -eq "") { continue }

    $match = $gameBoard | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $match) {
        $match = $gameBoard | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $pitcherRows = Get-ContextRows $match "pitcher"
    $bullpenRows = Get-ContextRows $match "bullpen"
    $injuryRows  = Get-ContextRows $match "injury"
    $lineupRows  = Get-ContextRows $match "lineup"

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

    $whyBullets = New-Object System.Collections.Generic.List[string]

    $whyBullets.Add("Market value: entry " + (Cents $o.Price) + ", model " + (Pct $o.ModelProbability) + ", edge +" + (Pct $o.EdgePct) + ".")

    if ($awayPitcher -or $homePitcher) {
        $whyBullets.Add("Pitcher context: $awayPitcher vs $homePitcher. ERA $awayEra vs $homeEra. WHIP $awayWhip vs $homeWhip.")
    }

    if ($awayBullpen -or $homeBullpen) {
        $whyBullets.Add("Bullpen context: away fatigue $awayBullpen, home fatigue $homeBullpen.")
    }

    if ($awayBpenFlags -or $homeBpenFlags) {
        $whyBullets.Add("Bullpen flags: away [$awayBpenFlags], home [$homeBpenFlags].")
    }

    if ($pickedInjuryRisk -or $opponentInjuryRisk) {
        $whyBullets.Add("Injury context: picked team risk $pickedInjuryRisk, opponent risk $opponentInjuryRisk.")
    }

    if ($injuryDetails -and $injuryDetails -notmatch "No recent") {
        $whyBullets.Add("Injury detail: $injuryDetails")
    }

    if ($awayLineup -or $homeLineup) {
        $whyBullets.Add("Lineups: away $awayLineup, home $homeLineup. Missing lineups increase uncertainty.")
    }

    if ($venue) {
        $whyBullets.Add("Venue: $venue.")
    }

    $reasonRows += [pscustomobject]@{
        Rank = $o.Rank
        Pick = $pick
        Game = $game
        Price = $o.Price
        ModelProbability = $o.ModelProbability
        EdgePct = $o.EdgePct
        RiskLevel = $o.RiskLevel
        WhyBullets = @($whyBullets)
    }
}

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("ASTRODDS 213B FIXED SCAN COVERAGE + PICK REASONS")
$lines.Add("")
$lines.Add("COVERAGE")
$lines.Add("Unique games found across available sources: $($allGames.Count)")
$lines.Add("Official games locked: $($officialRows.Count)")
$lines.Add("Official reasons built: $($reasonRows.Count)")
$lines.Add("Paper/review rows found: $paperCount")
$lines.Add("NO_BET rows found: $noBetCount")
$lines.Add("")

if ($allGames.Count -gt $officialRows.Count) {
    $lines.Add("Coverage check: Slate/context files include more games than the official picks. This means only a few passed the official filter.")
} else {
    $lines.Add("WARNING: Coverage still looks low. Check slate source.")
}

$lines.Add("")
$lines.Add("WHY THESE OFFICIAL PICKS")
$lines.Add("")

foreach ($r in $reasonRows | Sort-Object Rank) {
    $lines.Add("#$($r.Rank) $($r.Pick)")
    $lines.Add("Game: $($r.Game)")
    $lines.Add("Value: " + (Cents $r.Price) + " | Model: " + (Pct $r.ModelProbability) + " | Edge: +" + (Pct $r.EdgePct))
    $lines.Add("Risk: $($r.RiskLevel)")
    $lines.Add("Why:")

    foreach ($b in @($r.WhyBullets)) {
        $lines.Add("- $b")
    }

    $lines.Add("")
}

$lines.Add("IMPORTANT")
$lines.Add("These reasons explain why the model found value. They do NOT guarantee a win.")
$lines.Add("If lineups are missing, risk stays higher until confirmed.")

$result = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    uniqueGamesFound = $allGames.Count
    officialCount = $officialRows.Count
    officialReasonsBuilt = $reasonRows.Count
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

$result | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
