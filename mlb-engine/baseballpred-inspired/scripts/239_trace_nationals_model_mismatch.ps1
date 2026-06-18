$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt  = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-nationals-model-mismatch-trace-latest.json"

$targetGame = "Kansas City Royals @ Washington Nationals"
$targetPick = "Washington Nationals"

Write-Host ""
Write-Host "ASTRODDS 239 NATIONALS MODEL MISMATCH TRACE" -ForegroundColor Cyan
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

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }
    if ($data -is [System.Array]) { return @($data) }

    if ($data.aPicks) { return @(Normalize-Rows $data.aPicks) }
    if ($data.gameBoard) { return @(Normalize-Rows $data.gameBoard) }
    if ($data.rows) { return @(Normalize-Rows $data.rows) }
    if ($data.allRows) { return @(Normalize-Rows $data.allRows) }
    if ($data.officialPicks) { return @(Normalize-Rows $data.officialPicks) }
    if ($data.blockedPicks) { return @(Normalize-Rows $data.blockedPicks) }

    return @($data)
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

function Add-Hit($hits, $sourceName, $path, $row) {
    $game = Get-Val $row @("Game","game")
    $pick = Get-Val $row @("Pick","pick")

    if ($game -ne $script:targetGame -and $game -notlike "*Washington Nationals*") {
        return
    }

    if ($pick -ne "" -and $pick -ne $script:targetPick -and $pick -notlike "*Washington*") {
        return
    }

    $hits.Add([pscustomobject]@{
        Source = $sourceName
        File = $path
        LastWriteTime = if (Test-Path $path) { (Get-Item $path).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "" }
        Game = $game
        Pick = $pick
        Decision = Get-Val $row @("Decision","FinalDecision","status","category")
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
    })
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

$hits = New-Object System.Collections.Generic.List[object]

foreach ($f in $files) {
    $path = $f.Path
    if (!(Test-Path $path)) { continue }

    if ($f.Type -eq "csv") {
        $rows = Safe-Csv $path
        foreach ($r in $rows) {
            Add-Hit $hits $f.Name $path $r
        }
    } else {
        $json = Read-JsonSafe $path
        $rows = @(Normalize-Rows $json)
        foreach ($r in $rows) {
            Add-Hit $hits $f.Name $path $r
        }
    }
}

$hitsArray = @($hits)

$has76 = @($hitsArray | Where-Object {
    "$($_.PublicModel)" -match "76|0\.76" -or "$($_.FullSlateModel)" -match "76|0\.76"
})

$has635 = @($hitsArray | Where-Object {
    "$($_.PublicModel)" -match "63\.5|0\.634|0\.635" -or
    "$($_.FullSlateModel)" -match "63\.5|0\.634|0\.635"
})

$lines = @()
$lines += "ASTRODDS 239 NATIONALS MODEL MISMATCH TRACE"
$lines += ""
$lines += "Target: $targetPick | $targetGame"
$lines += "Rows found: $($hitsArray.Count)"
$lines += "Rows showing 76%: $($has76.Count)"
$lines += "Rows showing 63.5%: $($has635.Count)"
$lines += ""

$lines += "TRACE ROWS"
foreach ($h in $hitsArray) {
    $lines += "- Source=$($h.Source)"
    $lines += "  File=$($h.File)"
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
$lines += "- If 76% appears only in public_board/locked_official, it is probably stale or from the wrong promotion layer."
$lines += "- If 63.5% appears in full_slate/ranker/context, the calibrated context model is likely 63.5%."
$lines += "- Do not unlock Nationals automatically unless the mismatch source is repaired."
$lines += ""
$lines += "NEXT"
$lines += "If 76% is stale, patch public board generator to use the full slate model or downgrade mismatch picks to REVIEW_ONLY."

$hitsArray | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    targetGame = $targetGame
    targetPick = $targetPick
    rowsFound = $hitsArray.Count
    rowsShowing76 = $has76.Count
    rowsShowing635 = $has635.Count
    recommendation = "Trace the source of 76%. Keep blocked until mismatch source is fixed."
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
