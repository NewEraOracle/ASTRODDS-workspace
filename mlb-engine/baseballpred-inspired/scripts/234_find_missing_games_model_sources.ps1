$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$processed = Join-Path $root "mlb-engine\data\processed"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$mergedSlate = Join-Path $astro "ASTRODDS-complete-mlb-slate-merged-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-missing-games-model-source-audit-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-missing-games-model-source-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-missing-games-model-source-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 234 MISSING GAMES MODEL SOURCE AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FIND WHY FULL SLATE IS INCOMPLETE" -ForegroundColor Cyan
Write-Host ""

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Game($game) {
    $awayTeamName = ""
    $homeTeamName = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    }

    return [pscustomobject]@{
        Away = $awayTeamName
        Home = $homeTeamName
        AwayNorm = Normalize-Team $awayTeamName
        HomeNorm = Normalize-Team $homeTeamName
        GameNorm = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
    }
}

function Clean-Line($s) {
    if ($null -eq $s) { return "" }
    $x = "$s".Trim()
    if ($x.Length -gt 260) { return $x.Substring(0,260) }
    return $x
}

if (!(Test-Path $mergedSlate)) {
    Write-Host "ERROR: Missing merged slate from 233:" -ForegroundColor Red
    Write-Host $mergedSlate
    exit 0
}

$mergedRows = Safe-Csv $mergedSlate

$missingRows = @($mergedRows | Where-Object {
    "$($_.InAstroddsSlate)" -ne "YES"
})

$contextOnlyRows = @($mergedRows | Where-Object {
    "$($_.Decision)" -eq "ASTRODDS_CONTEXT_ONLY_NEEDS_GATE"
})

$allProblemRows = @()
$allProblemRows += @($missingRows)
$allProblemRows += @($contextOnlyRows)

# De-dupe by GamePk where possible, else by Game.
$seen = @{}
$problemGames = @()

foreach ($r in $allProblemRows) {
    $key = "$($r.GamePk)"
    if ($key -eq "") { $key = "$($r.Game)" }

    if (!$seen.ContainsKey($key)) {
        $seen[$key] = $true
        $problemGames += ,$r
    }
}

$sourceFiles = @()

foreach ($dir in @($astro, $processed)) {
    if (Test-Path $dir) {
        $sourceFiles += @(Get-ChildItem -Path $dir -File -ErrorAction SilentlyContinue |
            Where-Object {
                ($_.Extension -in @(".csv", ".json", ".txt")) -and
                $_.Length -lt 8000000
            })
    }
}

$sourceFiles = @($sourceFiles | Sort-Object FullName -Unique)

$hitRows = @()

foreach ($pg in $problemGames) {
    $game = "$($pg.Game)"
    $split = Split-Game $game

    $awayNorm = $split.AwayNorm
    $homeNorm = $split.HomeNorm

    foreach ($file in $sourceFiles) {
        try {
            $lines = Get-Content $file.FullName -ErrorAction Stop

            for ($i = 0; $i -lt $lines.Count; $i++) {
                $lineRaw = "$($lines[$i])"
                $lineNorm = Normalize-Team $lineRaw

                $hasAway = $lineNorm -like "*$awayNorm*"
                $hasHome = $lineNorm -like "*$homeNorm*"

                if ($hasAway -and $hasHome) {
                    $hitRows += ,[pscustomobject]@{
                        Game = $game
                        GamePk = "$($pg.GamePk)"
                        Away = $split.Away
                        Home = $split.Home
                        Issue = "$($pg.MissingReason)"
                        SourceFile = $file.FullName
                        LineNumber = $i + 1
                        Line = Clean-Line $lineRaw
                    }
                }
            }
        } catch {
            continue
        }
    }
}

# Search generator scripts for likely filters/limits.
$scriptHits = @()
$patterns = @(
    "full-slate",
    "full_slate",
    "top",
    "limit",
    "Select-Object -First",
    "daily_pick",
    "aPicks",
    "ranker",
    "context_final",
    "public_board",
    "moneyline",
    "modelProbability",
    "marketProbability",
    "paperOnly",
    "NO_ASTRODDS_MODEL_YET",
    "ASTRODDS-full-slate-context-final-latest.csv"
)

if (Test-Path $scripts) {
    $scriptFiles = Get-ChildItem -Path $scripts -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".ps1", ".py", ".js", ".ts") -and $_.Length -lt 4000000 }

    foreach ($sf in $scriptFiles) {
        try {
            $matches = Select-String -LiteralPath $sf.FullName -Pattern $patterns -SimpleMatch -ErrorAction SilentlyContinue

            foreach ($m in @($matches)) {
                $scriptHits += ,[pscustomobject]@{
                    File = $m.Path
                    LineNumber = $m.LineNumber
                    Pattern = "$($m.Pattern)"
                    Line = Clean-Line $m.Line
                }
            }
        } catch {}
    }
}

$missingHitCount = @($hitRows | Where-Object { $_.SourceFile -ne "" }).Count

$linesOut = @()
$linesOut += "ASTRODDS 234 MISSING GAMES MODEL SOURCE AUDIT"
$linesOut += ""
$linesOut += "Problem games checked: $($problemGames.Count)"
$linesOut += "Source files scanned: $($sourceFiles.Count)"
$linesOut += "Source hits found: $($hitRows.Count)"
$linesOut += ""

$linesOut += "PROBLEM GAMES"
foreach ($g in $problemGames) {
    $linesOut += "- $($g.Game) | gamePk=$($g.GamePk) | inSlate=$($g.InAstroddsSlate) | decision=$($g.Decision)"
    if ("$($g.MissingReason)" -ne "") {
        $linesOut += "  Issue: $($g.MissingReason)"
    }
}
$linesOut += ""

$linesOut += "SOURCE HITS BY GAME"
foreach ($g in $problemGames) {
    $gameHits = @($hitRows | Where-Object { $_.Game -eq "$($g.Game)" })

    $linesOut += "$($g.Game)"
    if ($gameHits.Count -eq 0) {
        $linesOut += "- No source hits found in .astrodds / processed files."
    } else {
        foreach ($h in ($gameHits | Select-Object -First 12)) {
            $linesOut += "- $($h.SourceFile):$($h.LineNumber) :: $($h.Line)"
        }

        if ($gameHits.Count -gt 12) {
            $linesOut += "- ... plus $($gameHits.Count - 12) more hits"
        }
    }

    $linesOut += ""
}

$linesOut += "LIKELY GENERATOR / FILTER HITS"
foreach ($h in ($scriptHits | Select-Object -First 120)) {
    $linesOut += "- $($h.File):$($h.LineNumber) [$($h.Pattern)] :: $($h.Line)"
}
if ($scriptHits.Count -eq 0) {
    $linesOut += "- No script hits found."
}
$linesOut += ""

$linesOut += "INTERPRETATION"
$linesOut += "- If missing games appear in raw/source files, the full-slate generator is filtering them out."
$linesOut += "- If missing games do not appear anywhere, the upstream market/model scan never fetched/scored them."
$linesOut += "- Do not claim full-slate best bets until every MLB schedule game has a scored ASTRODDS row or an explicit NO_MODEL_YET block."
$linesOut += ""

$linesOut += "NEXT PATCH"
$linesOut += "235 should build a schedule-first full-slate model input:"
$linesOut += "- start from MLB schedule 15 games"
$linesOut += "- merge market prices if available"
$linesOut += "- merge model probabilities if available"
$linesOut += "- mark missing model/market as NO_MODEL_YET"
$linesOut += "- only run official gate on rows with model+market+lineups"

$hitRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    problemGamesChecked = $problemGames.Count
    sourceFilesScanned = $sourceFiles.Count
    sourceHitsFound = $hitRows.Count
    scriptHitsFound = $scriptHits.Count
    recommendation = "Use schedule-first full-slate builder. Missing games must become explicit NO_MODEL_YET rows instead of disappearing."
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($linesOut -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($linesOut -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
