$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$controlBoard = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"
$publicBoard = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"

$outCsv = Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.json"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 236 ALL CONTEXT SMART GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - EVALUATE EVERY ASTRODDS CONTEXT ROW" -ForegroundColor Cyan
Write-Host ""

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }
    if ($data -is [System.Array]) { return @($data) }
    if ($data.aPicks) { return @(Normalize-Rows $data.aPicks) }
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

function Num($v) {
    if ($null -eq $v) { return $null }

    $s = "$v".Trim()
    if ($s -eq "") { return $null }

    $s = $s.Replace("%", "")
    $s = $s.Replace("¢", "")
    $s = $s.Replace(",", ".")

    $n = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }

    return $null
}

function Prob-Num($v) {
    $n = Num $v
    if ($null -eq $n) { return $null }

    if ($n -gt 1 -and $n -le 100) {
        $n = $n / 100
    }

    if ($n -gt 0 -and $n -lt 1) {
        return $n
    }

    return $null
}

function EdgePct-Num($v) {
    $n = Num $v
    if ($null -eq $n) { return $null }

    if ([math]::Abs($n) -le 1) {
        $n = $n * 100
    }

    return $n
}

function Pct($v) {
    $n = Prob-Num $v
    if ($null -eq $n) { return "N/A" }
    return ($n * 100).ToString("0.0", $culture) + "%"
}

function EdgeText($v) {
    $n = EdgePct-Num $v
    if ($null -eq $n) { return "N/A" }
    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Prob-Num $v
    if ($null -eq $n) { return "N/A" }
    return ($n * 100).ToString("0.0", $culture) + "¢"
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

    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

$rows = Safe-Csv $controlBoard

if ($rows.Count -eq 0) {
    Write-Host "ERROR: Control board missing. Run 235 first." -ForegroundColor Red
    Write-Host $controlBoard
    exit 0
}

$public = Read-JsonSafe $publicBoard
$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$publicKeys = @{}

foreach ($p in $publicAPicks) {
    $game = Get-Val $p @("game", "Game")
    $pick = Get-Val $p @("pick", "Pick")

    if ($game -ne "" -and $pick -ne "") {
        $key = (Split-Game $game) + "|" + (Normalize-Team $pick)
        $publicKeys[$key] = $true
    }
}

$gateRows = @()

foreach ($r in $rows) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $coverage = Get-Val $r @("CoverageStatus")
    $mlbStatus = Get-Val $r @("MlbStatus")
    $awayLineup = Get-Val $r @("AwayLineupStatus")
    $homeLineup = Get-Val $r @("HomeLineupStatus")

    $model = Prob-Num (Get-Val $r @("ModelProbability"))
    $market = Prob-Num (Get-Val $r @("MarketProbability", "Price"))
    $edgePct = EdgePct-Num (Get-Val $r @("EdgePct"))

    $hard = @()
    $warn = @()

    $sourceType = "CONTEXT_ONLY"
    $publicKey = (Split-Game $game) + "|" + (Normalize-Team $pick)

    if ($publicKeys.ContainsKey($publicKey)) {
        $sourceType = "PUBLIC_APICK"
    }

    if ($coverage -eq "NO_MODEL_YET") {
        $hard += "NO_MODEL_YET: missing from ASTRODDS model slate"
    }

    if ($coverage -eq "NEEDS_SMART_GATE") {
        $warn += "was not evaluated by previous smart gate"
    }

    if ($pick -eq "") {
        $hard += "missing pick"
    }

    if ($null -eq $model) {
        $hard += "missing or invalid model probability"
    }

    if ($null -eq $market) {
        $hard += "missing or invalid market probability"
    }

    if ($null -eq $edgePct) {
        $hard += "missing edge"
    } elseif ($edgePct -lt 5) {
        $hard += "edge below official threshold 5%"
    }

    if ($awayLineup -ne "confirmed" -or $homeLineup -ne "confirmed") {
        $hard += "lineups not fully confirmed"
    }

    if ("$mlbStatus".ToLower() -match "final|suspended") {
        $hard += "game status not eligible: $mlbStatus"
    }

    $decision = "CLIENT_OFFICIAL_SEND_OK"

    if ($hard.Count -gt 0) {
        $decision = "BLOCKED_FOR_REVIEW"
    } elseif ($sourceType -ne "PUBLIC_APICK") {
        $decision = "REVIEW_ONLY_CONTEXT"
        $warn += "context-only row needs model-source verification before client official"
    }

    $gateRows += ,[pscustomobject]@{
        Decision = $decision
        SourceType = $sourceType
        CoverageStatus = $coverage
        Game = $game
        Pick = $pick
        MlbStatus = $mlbStatus
        Price = Cents $market
        ModelProbability = Pct $model
        MarketProbability = Pct $market
        Edge = EdgeText $edgePct
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
    }
}

$sendOk = @($gateRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$reviewContext = @($gateRows | Where-Object { $_.Decision -eq "REVIEW_ONLY_CONTEXT" }).Count
$blocked = @($gateRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count
$noModel = @($gateRows | Where-Object { $_.HardBlocks -like "*NO_MODEL_YET*" }).Count

$gateRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 236 ALL CONTEXT SMART GATE"
$lines += ""
$lines += "Rows evaluated: $($gateRows.Count)"
$lines += "CLIENT_OFFICIAL_SEND_OK: $sendOk"
$lines += "REVIEW_ONLY_CONTEXT: $reviewContext"
$lines += "BLOCKED_FOR_REVIEW: $blocked"
$lines += "NO_MODEL_YET: $noModel"
$lines += ""

$lines += "OFFICIAL SEND_OK"
$okRows = @($gateRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" })
if ($okRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($x in $okRows) {
        $lines += "- $($x.Pick) | $($x.Game) | Price=$($x.Price) | Model=$($x.ModelProbability) | Edge=$($x.Edge)"
    }
}
$lines += ""

$lines += "REVIEW CONTEXT CANDIDATES"
$reviewRows = @($gateRows | Where-Object { $_.Decision -eq "REVIEW_ONLY_CONTEXT" })
if ($reviewRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($x in $reviewRows) {
        $lines += "- $($x.Pick) | $($x.Game) | Price=$($x.Price) | Model=$($x.ModelProbability) | Edge=$($x.Edge)"
        if ($x.Warnings -ne "") { $lines += "  Warn: $($x.Warnings)" }
    }
}
$lines += ""

$lines += "BLOCKED"
foreach ($x in ($gateRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" })) {
    $lines += "- $($x.Pick) | $($x.Game) | coverage=$($x.CoverageStatus) | lineups=$($x.AwayLineupStatus)/$($x.HomeLineupStatus)"
    if ($x.HardBlocks -ne "") { $lines += "  Hard: $($x.HardBlocks)" }
}
$lines += ""

$lines += "IMPORTANT"
$lines += "This evaluates every ASTRODDS context row."
$lines += "Context-only rows are REVIEW_ONLY_CONTEXT until we verify the model/market source."
$lines += "NO_MODEL_YET games still need upstream model/market scoring."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rowsEvaluated = $gateRows.Count
    sendOk = $sendOk
    reviewOnlyContext = $reviewContext
    blocked = $blocked
    noModelYet = $noModel
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
