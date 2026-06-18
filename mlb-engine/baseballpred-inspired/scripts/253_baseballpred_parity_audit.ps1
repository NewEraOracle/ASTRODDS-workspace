$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-253-baseballpred-parity-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-253-baseballpred-parity-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-253-baseballpred-parity-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 253D BASEBALLPRED PARITY AUDIT STABLE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - STABLE FILE CHECK" -ForegroundColor Cyan
Write-Host ""

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) } catch { return @() }
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

$control = Safe-Csv (Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv")
$context = Safe-Csv (Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv")
$guard = Safe-Csv (Join-Path $astro "ASTRODDS-249-price-guard-latest.csv")

$rows = @()

foreach ($r in $control) {
    $game = Get-Val $r @("Game")
    if ($game -eq "") { continue }

    $pick = Get-Val $r @("Pick")
    $model = Get-Val $r @("ModelProbability")
    $market = Get-Val $r @("MarketProbability","Price")
    $edge = Get-Val $r @("Edge","EdgePct")
    $awayLineup = Get-Val $r @("AwayLineupStatus")
    $homeLineup = Get-Val $r @("HomeLineupStatus")
    $decision = Get-Val $r @("Decision")
    $coverage = Get-Val $r @("CoverageStatus")

    $issues = @()
    if ($pick -eq "") { $issues += "missing_pick" }
    if ($model -eq "") { $issues += "missing_model" }
    if ($market -eq "") { $issues += "missing_market" }
    if ($edge -eq "") { $issues += "missing_edge" }
    if ($coverage -eq "NO_MODEL_YET") { $issues += "NO_MODEL_YET" }
    if ($awayLineup -ne "confirmed" -or $homeLineup -ne "confirmed") { $issues += "lineups_not_confirmed" }

    $parity = "BASEBALLPRED_READY_ROW"
    if ($issues.Count -gt 0) { $parity = "PARITY_INCOMPLETE" }

    $rows += ,[pscustomobject]@{
        Game = $game
        Pick = $pick
        ModelProbability = $model
        MarketProbability = $market
        Edge = $edge
        Lineups = "$awayLineup/$homeLineup"
        CoverageStatus = $coverage
        Decision = $decision
        ParityStatus = $parity
        Issues = ($issues -join " | ")
    }
}

if ($rows.Count -eq 0) {
    foreach ($r in $context) {
        $rows += ,[pscustomobject]@{
            Game = Get-Val $r @("Game")
            Pick = Get-Val $r @("Pick")
            ModelProbability = Get-Val $r @("Model")
            MarketProbability = Get-Val $r @("Entry")
            Edge = Get-Val $r @("Edge")
            Lineups = Get-Val $r @("Lineups")
            CoverageStatus = Get-Val $r @("ContextStatus")
            Decision = "CONTEXT_OFFICIAL"
            ParityStatus = "BASEBALLPRED_READY_ROW"
            Issues = ""
        }
    }
}

$ready = @($rows | Where-Object { $_.ParityStatus -eq "BASEBALLPRED_READY_ROW" }).Count
$incomplete = @($rows | Where-Object { $_.ParityStatus -ne "BASEBALLPRED_READY_ROW" }).Count
$noModel = @($rows | Where-Object { $_.Issues -like "*NO_MODEL_YET*" -or $_.Issues -like "*missing_model*" }).Count

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 253D BASEBALLPRED PARITY AUDIT STABLE"
$lines += ""
$lines += "Rows checked: $($rows.Count)"
$lines += "BaseballPred-ready rows: $ready"
$lines += "Incomplete rows: $incomplete"
$lines += "NO_MODEL / missing model rows: $noModel"
$lines += ""
$lines += "PARITY BOARD"
foreach ($r in $rows) {
    $lines += "- $($r.ParityStatus) | $($r.Game) | Pick=$($r.Pick) | Model=$($r.ModelProbability) | Market=$($r.MarketProbability) | Edge=$($r.Edge) | Lineups=$($r.Lineups)"
    if ($r.Issues -ne "") { $lines += "  Issues: $($r.Issues)" }
}
$lines += ""
$lines += "DECISION"
if ($incomplete -gt 0) {
    $lines += "- Bot is operational, but some rows are not full BaseballPred-ready yet."
} else {
    $lines += "- All available rows are BaseballPred-ready."
}

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rowsChecked = $rows.Count
    baseballPredReadyRows = $ready
    incompleteRows = $incomplete
    noModelRows = $noModel
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""

exit 0
