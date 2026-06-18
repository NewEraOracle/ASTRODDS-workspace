$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$processed = Join-Path $root "mlb-engine\data\processed"

$outTxt  = Join-Path $astro "ASTRODDS-lineup-source-connection-audit-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-lineup-source-connection-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-lineup-source-connection-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 222 LINEUP SOURCE CONNECTION AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY" -ForegroundColor Cyan
Write-Host ""

function Safe-ReadCsv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Safe-ReadJson($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Has-Col($rows, $name) {
    if ($rows.Count -eq 0) { return $false }
    return $null -ne $rows[0].PSObject.Properties[$name]
}

function First-Val($row, $names) {
    foreach ($n in @($names)) {
        if ($null -ne $row.PSObject.Properties[$n] -and $null -ne $row.$n -and "$($row.$n)".Trim() -ne "") {
            return "$($row.$n)".Trim()
        }
    }
    return ""
}

$knownFiles = @(
    (Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"),
    (Join-Path $astro "ASTRODDS-full-slate-context-input-latest.csv"),
    (Join-Path $astro "VVS-pitcher-context-latest.csv"),
    (Join-Path $astro "VVS-bullpen-context-latest.csv"),
    (Join-Path $processed "mlb_lineup_player_features.csv"),
    (Join-Path $processed "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup.csv"),
    (Join-Path $processed "mlb_moneyline_features_with_pitchers_bullpen_weather_lineup_injuries.csv")
)

$extraCandidates = @()

foreach ($dir in @($astro, $processed)) {
    if (Test-Path $dir) {
        $extraCandidates += @(Get-ChildItem -Path $dir -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match "lineup|player|context|slate" -and
                ($_.Extension -eq ".csv" -or $_.Extension -eq ".json")
            } |
            Select-Object -ExpandProperty FullName)
    }
}

$candidates = @($knownFiles + $extraCandidates | Sort-Object -Unique)

$auditRows = @()

foreach ($file in $candidates) {
    if (!(Test-Path $file)) {
        $auditRows += ,[pscustomobject]@{
            File = $file
            Exists = "NO"
            Rows = 0
            HasGame = "NO"
            HasPick = "NO"
            HasAwayLineupStatus = "NO"
            HasHomeLineupStatus = "NO"
            ConfirmedRows = 0
            MissingRows = 0
            SampleGame = ""
            SampleStatus = ""
            Verdict = "missing file"
        }
        continue
    }

    $rows = @()

    if ($file.ToLower().EndsWith(".csv")) {
        $rows = Safe-ReadCsv $file
    } elseif ($file.ToLower().EndsWith(".json")) {
        $json = Safe-ReadJson $file
        if ($null -ne $json) {
            if ($json -is [System.Array]) {
                $rows = @($json)
            } elseif ($json.gameBoard) {
                $rows = @($json.gameBoard)
            } elseif ($json.rows) {
                $rows = @($json.rows)
            } elseif ($json.aPicks) {
                $rows = @($json.aPicks)
            } else {
                $rows = @($json)
            }
        }
    }

    $hasGame = Has-Col $rows "game"
    $hasPick = Has-Col $rows "pick"
    $hasAwayLineup = Has-Col $rows "awayLineupStatus"
    $hasHomeLineup = Has-Col $rows "homeLineupStatus"

    $confirmed = 0
    $missing = 0

    foreach ($r in $rows) {
        $away = First-Val $r @("awayLineupStatus", "away_lineup_status")
        $homeStatus = First-Val $r @("homeLineupStatus", "home_lineup_status")
        $status = First-Val $r @("lineupStatus", "status")

        if ($away -eq "confirmed" -or $homeStatus -eq "confirmed" -or $status -eq "confirmed") {
            $confirmed++
        }

        if ($away -eq "missing" -or $homeStatus -eq "missing" -or $status -eq "missing") {
            $missing++
        }
    }

    $sampleGame = ""
    $sampleStatus = ""

    if ($rows.Count -gt 0) {
        $sampleGame = First-Val $rows[0] @("game", "Game", "matchup")
        $a = First-Val $rows[0] @("awayLineupStatus", "away_lineup_status")
        $h = First-Val $rows[0] @("homeLineupStatus", "home_lineup_status")
        $sampleStatus = "away=$a home=$h"
    }

    $verdict = "no lineup status columns"
    if ($hasAwayLineup -or $hasHomeLineup) {
        if ($confirmed -gt 0) {
            $verdict = "has confirmed lineup data"
        } elseif ($missing -gt 0) {
            $verdict = "lineup columns exist but rows are missing"
        } else {
            $verdict = "lineup columns exist but no confirmed/missing values"
        }
    }

    $auditRows += ,[pscustomobject]@{
        File = $file
        Exists = "YES"
        Rows = $rows.Count
        HasGame = if ($hasGame) { "YES" } else { "NO" }
        HasPick = if ($hasPick) { "YES" } else { "NO" }
        HasAwayLineupStatus = if ($hasAwayLineup) { "YES" } else { "NO" }
        HasHomeLineupStatus = if ($hasHomeLineup) { "YES" } else { "NO" }
        ConfirmedRows = $confirmed
        MissingRows = $missing
        SampleGame = $sampleGame
        SampleStatus = $sampleStatus
        Verdict = $verdict
    }
}

$script37 = Join-Path $root "mlb-engine\baseballpred-inspired\scripts\37_full_slate_context_final_gate.py"
$script198 = Join-Path $root "mlb-engine\baseballpred-inspired\scripts\198_baseballpred_full_slate_ranker.py"

$scriptHits = @()

foreach ($s in @($script37, $script198)) {
    if (Test-Path $s) {
        $matches = Select-String -LiteralPath $s -Pattern @("awayLineupStatus", "homeLineupStatus", "lineup", "confirmed", "missing", "paperOnly", "FULL_CONTEXT_REVIEW") -SimpleMatch -ErrorAction SilentlyContinue
        foreach ($m in @($matches)) {
            $line = "$($m.Line)".Trim()
            if ($line.Length -gt 220) { $line = $line.Substring(0, 220) }
            $scriptHits += ,[pscustomobject]@{
                File = $m.Path
                LineNumber = $m.LineNumber
                Pattern = $m.Pattern
                Line = $line
            }
        }
    }
}

$confirmedFiles = @($auditRows | Where-Object { [int]$_.ConfirmedRows -gt 0 })
$lineupFiles = @($auditRows | Where-Object { $_.HasAwayLineupStatus -eq "YES" -or $_.HasHomeLineupStatus -eq "YES" })

$lines = @()
$lines += "ASTRODDS 222 LINEUP SOURCE CONNECTION AUDIT"
$lines += ""
$lines += "Files checked: $($auditRows.Count)"
$lines += "Files with lineup status columns: $($lineupFiles.Count)"
$lines += "Files with confirmed lineup rows: $($confirmedFiles.Count)"
$lines += ""

$lines += "LINEUP FILE AUDIT"
foreach ($r in $auditRows) {
    $lines += "- $($r.File)"
    $lines += "  Exists=$($r.Exists) Rows=$($r.Rows) AwayLineupCol=$($r.HasAwayLineupStatus) HomeLineupCol=$($r.HasHomeLineupStatus) Confirmed=$($r.ConfirmedRows) Missing=$($r.MissingRows)"
    $lines += "  Verdict: $($r.Verdict)"
    if ($r.SampleGame -ne "") {
        $lines += "  Sample: $($r.SampleGame) | $($r.SampleStatus)"
    }
}
$lines += ""

$lines += "SCRIPT LINEUP LOGIC HITS"
foreach ($h in ($scriptHits | Select-Object -First 120)) {
    $lines += "- $($h.File):$($h.LineNumber) [$($h.Pattern)] :: $($h.Line)"
}
if ($scriptHits.Count -eq 0) {
    $lines += "- No script hits found."
}
$lines += ""

$lines += "INTERPRETATION"
if ($confirmedFiles.Count -eq 0) {
    $lines += "- No confirmed lineup source was found in the checked files."
    $lines += "- The bot should keep lineup-sensitive picks as REVIEW_ONLY/BLOCKED until confirmed lineups exist."
} else {
    $lines += "- Confirmed lineup data exists somewhere. Next step: connect it into 37_full_slate_context_final_gate.py."
}

$lines += ""
$lines += "NEXT STEP"
$lines += "223 should either:"
$lines += "A) connect a confirmed lineup source into the full slate context gate, or"
$lines += "B) create a time-aware rule: before lineups are confirmed, downgrade to REVIEW_ONLY; after confirmed, allow client-safe evaluation."

$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    filesChecked = $auditRows.Count
    filesWithLineupColumns = $lineupFiles.Count
    filesWithConfirmedLineups = $confirmedFiles.Count
    recommendation = if ($confirmedFiles.Count -gt 0) { "Connect confirmed lineup file to full slate context." } else { "Keep lineup-sensitive picks blocked/review-only until lineup source is available." }
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""

