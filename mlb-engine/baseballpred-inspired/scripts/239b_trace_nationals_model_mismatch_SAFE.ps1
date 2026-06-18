$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt  = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-SAFE-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-SAFE-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-SAFE-latest.json"

$targetGame = "Kansas City Royals @ Washington Nationals"
$targetPick = "Washington Nationals"

Write-Host ""
Write-Host "ASTRODDS 239B NATIONALS MODEL MISMATCH TRACE SAFE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FIND 76% VS 63.5%" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }

    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
    }

    return ""
}

function Normalize-Rows($json) {
    if ($null -eq $json) { return @() }
    if ($json -is [System.Array]) { return @($json) }

    $rows = @()

    if ($json.aPicks) { $rows += @($json.aPicks) }
    if ($json.gameBoard) { $rows += @($json.gameBoard) }
    if ($json.rows) { $rows += @($json.rows) }
    if ($json.allRows) { $rows += @($json.allRows) }
    if ($json.officialPicks) { $rows += @($json.officialPicks) }
    if ($json.reviewOnlyPicks) { $rows += @($json.reviewOnlyPicks) }
    if ($json.blockedPicks) { $rows += @($json.blockedPicks) }

    if ($rows.Count -eq 0) {
        $rows += ,$json
    }

    return @($rows)
}

function Make-Hit($sourceName, $path, $row) {
    $game = Get-Val $row @("Game","game")
    $pick = Get-Val $row @("Pick","pick")

    $gameHit = $false
    $pickHit = $false

    if ($game -eq $script:targetGame -or $game -like "*Washington Nationals*" -or $game -like "*Kansas City Royals*") {
        $gameHit = $true
    }

    if ($pick -eq "" -or $pick -eq $script:targetPick -or $pick -like "*Washington*") {
        $pickHit = $true
    }

    if (-not ($gameHit -and $pickHit)) {
        return $null
    }

    $lastWrite = ""
    if (Test-Path $path) {
        $lastWrite = (Get-Item $path).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
    }

    return [pscustomobject]@{
        Source = $sourceName
        File = $path
        LastWriteTime = $lastWrite
        Game = $game
        Pick = $pick
        Decision = Get-Val $row @("Decision","FinalDecision","status","category","clientSafeDecision")
        Price = Get-Val $row @("Price","price","market","marketProbability")
        PublicModel = Get-Val $row @("PublicModel","model","modelProbability","ModelProbability")
        FullSlateModel = Get-Val $row @("FullSlateModel","fullSlateModel","fullSlateModelProbability")
        MarketProbability = Get-Val $row @("MarketProbability","marketProbability")
        Edge = Get-Val $row @("Edge","edge","EdgePct","edgePct")
        PaperOnly = Get-Val $row @("PaperOnly","paperOnly")
        AwayLineup = Get-Val $row @("AwayLineupStatus","awayLineupStatus")
        HomeLineup = Get-Val $row @("HomeLineupStatus","homeLineupStatus")
        HardBlocks = Get-Val $row @("HardBlocks","hardBlocks")
        Warnings = Get-Val $row @("Warnings","warnings")
        FinalReason = Get-Val $row @("FinalReason","Reason","reason")
    }
}

$files = @(
    @{ Name="public_board"; Path=(Join-Path $astro "ASTRODDS-public-board-categories-latest.json"); Type="json" },
    @{ Name="locked_official"; Path=(Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"); Type="json" },
    @{ Name="full_slate_context"; Path=(Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"); Type="csv" },
    @{ Name="smart_live_gate_228"; Path=(Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"); Type="csv" },
    @{ Name="schedule_first_235"; Path=(Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"); Type="csv" },
    @{ Name="all_context_gate_236"; Path=(Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.csv"); Type="csv" },
    @{ Name="final_reconciled_237"; Path=(Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.csv"); Type="csv" },
    @{ Name="client_safe_public_219"; Path=(Join-Path $astro "ASTRODDS-client-safe-public-board-latest.csv"); Type="csv" },
    @{ Name="ranker_original"; Path=(Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"); Type="json" },
    @{ Name="ranker_client_safe_220"; Path=(Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.csv"); Type="csv" }
)

$hits = @()

foreach ($f in $files) {
    $path = $f.Path
    if (!(Test-Path $path)) { continue }

    if ($f.Type -eq "csv") {
        $rows = Safe-Csv $path
    } else {
        $json = Read-JsonSafe $path
        $rows = Normalize-Rows $json
    }

    foreach ($r in $rows) {
        $hit = Make-Hit $f.Name $path $r
        if ($null -ne $hit) {
            $hits += ,$hit
        }
    }
}

$has76 = @($hits | Where-Object {
    "$($_.PublicModel)" -match "76|0\.76" -or
    "$($_.FullSlateModel)" -match "76|0\.76"
})

$has635 = @($hits | Where-Object {
    "$($_.PublicModel)" -match "63\.5|0\.634|0\.635" -or
    "$($_.FullSlateModel)" -match "63\.5|0\.634|0\.635"
})

$lines = @()
$lines += "ASTRODDS 239B NATIONALS MODEL MISMATCH TRACE SAFE"
$lines += ""
$lines += "Target: $targetPick | $targetGame"
$lines += "Rows found: $($hits.Count)"
$lines += "Rows showing 76%: $($has76.Count)"
$lines += "Rows showing 63.5%: $($has635.Count)"
$lines += ""

$lines += "TRACE ROWS"
foreach ($h in $hits) {
    $lines += "- Source=$($h.Source)"
    $lines += "  LastWrite=$($h.LastWriteTime)"
    $lines += "  Decision=$($h.Decision)"
    $lines += "  Pick=$($h.Pick) | Game=$($h.Game)"
    $lines += "  Price=$($h.Price) | PublicModel=$($h.PublicModel) | FullSlateModel=$($h.FullSlateModel) | Market=$($h.MarketProbability) | Edge=$($h.Edge)"
    $lines += "  PaperOnly=$($h.PaperOnly) | Lineups=$($h.AwayLineup)/$($h.HomeLineup)"
    if ($h.HardBlocks -ne "") { $lines += "  Hard=$($h.HardBlocks)" }
    if ($h.Warnings -ne "") { $lines += "  Warn=$($h.Warnings)" }
    if ($h.FinalReason -ne "") { $lines += "  Reason=$($h.FinalReason)" }
    $lines += ""
}

$lines += "INTERPRETATION"
$lines += "- If 76% appears only in public_board or locked_official, it is likely stale/wrong promotion data."
$lines += "- If 63.5% appears in full_slate/context/ranker, that is likely the cleaner calibrated context model."
$lines += "- Nationals should stay BLOCKED until the source mismatch is repaired."

$hits | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    targetGame = $targetGame
    targetPick = $targetPick
    rowsFound = $hits.Count
    rowsShowing76 = $has76.Count
    rowsShowing635 = $has635.Count
    recommendation = "Keep Nationals blocked until 76% source is proven valid or removed."
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
