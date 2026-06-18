$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$source = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"

$outJson = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$outCsv  = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.csv"

Write-Host ""
Write-Host "ASTRODDS MONEYLINE OFFICIAL SOURCE LOCK" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - OFFICIAL BUY ONLY" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $source)) {
    Write-Host "WARNING: Source file missing:" -ForegroundColor Yellow
    Write-Host $source
    exit 0
}

try {
    $json = Get-Content $source -Raw | ConvertFrom-Json
} catch {
    Write-Host "WARNING: Invalid JSON source. Cannot continue." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
    exit 0
}

$rawPicks = @()

if ($json.aPicks) {
    $rawPicks += @($json.aPicks)
}

if ($json.A_PICK) {
    $rawPicks += @($json.A_PICK)
}

if ($rawPicks.Count -eq 0) {
    Write-Host "WARNING: No aPicks found in public board." -ForegroundColor Yellow
    exit 0
}

function To-DoubleOrNull($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }

    $n = 0.0
    if ([double]::TryParse(
        $s,
        [System.Globalization.NumberStyles]::Any,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$n
    )) {
        return $n
    }

    return $null
}

$official = @()
$seen = @{}
$duplicates = 0

foreach ($p in $rawPicks) {
    $game = "$($p.game)".Trim()
    $pick = "$($p.pick)".Trim()
    $category = "$($p.category)".Trim()

    $marketConnected = $false
    if ($p.marketConnected -eq $true -or "$($p.marketConnected)" -eq "True" -or "$($p.marketConnected)" -eq "true") {
        $marketConnected = $true
    }

    $market = To-DoubleOrNull $p.market
    $model  = To-DoubleOrNull $p.model
    $edge   = To-DoubleOrNull $p.edge

    if ($game -eq "" -or $pick -eq "") { continue }
    if (!$marketConnected) { continue }
    if ($null -eq $market -or $market -le 0 -or $market -ge 1) { continue }
    if ($null -eq $model -or $model -le 0 -or $model -ge 1) { continue }
    if ($null -eq $edge -or $edge -le 0) { continue }

    $key = ($game.ToLower() + "|" + $pick.ToLower() + "|moneyline")

    if ($seen.ContainsKey($key)) {
        $duplicates++
        continue
    }

    $seen[$key] = $true

    $official += [pscustomobject]@{
        Rank             = 0
        Category         = "OFFICIAL"
        MarketType       = "MONEYLINE"
        Game             = $game
        Pick             = $pick
        GameTime         = "$($p.date)"
        Price            = [math]::Round($market, 4)
        ModelProbability = [math]::Round($model, 4)
        EdgePct          = [math]::Round(($edge * 100), 2)
        Stake            = if ($p.stake) { "$($p.stake)" } else { "5% bankroll" }
        RiskLevel        = if ($p.riskLevel) { "$($p.riskLevel)" } else { "medium" }
        Reason           = if ($p.reason) { "$($p.reason)" } else { "Clean public board official pick with market, model, and positive edge." }
        TelegramEligible = $true
        Source           = "ASTRODDS-public-board-categories-latest.json"
    }
}

$official = $official | Sort-Object EdgePct, ModelProbability -Descending

$rank = 1
$official = foreach ($row in $official) {
    $row.Rank = $rank
    $rank++
    $row
}

$official | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson
$official | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

Write-Host "OFFICIAL BUY ONLY" -ForegroundColor Green
Write-Host ""

if ($official.Count -eq 0) {
    Write-Host "No official moneyline picks locked." -ForegroundColor Yellow
} else {
    $official |
        Select-Object Rank, Pick, Game, Price, ModelProbability, EdgePct, Stake, RiskLevel |
        Format-Table -AutoSize
}

Write-Host ""
Write-Host "AUDIT SUMMARY" -ForegroundColor Cyan
Write-Host "Official count: $($official.Count)"
Write-Host "Duplicates removed: $duplicates"
Write-Host "Source used: $source"
Write-Host "Output JSON: $outJson"
Write-Host "Output CSV: $outCsv"
Write-Host ""
Write-Host "WARNING: No full-slate calibrated probability source is locked yet. Only public board official aPicks are official." -ForegroundColor Yellow
Write-Host ""
