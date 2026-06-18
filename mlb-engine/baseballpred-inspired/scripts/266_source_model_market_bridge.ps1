$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$modelCsv = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv"
$controlCsv = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"
$guardCsv = Join-Path $astro "ASTRODDS-249-price-guard-latest.csv"

$outCsv = Join-Path $astro "ASTRODDS-266-source-model-market-bridge-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-266-source-model-market-bridge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-266-source-model-market-bridge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 266 SOURCE MODEL + MARKET BRIDGE" -ForegroundColor Cyan
Write-Host "Connects baseline model to existing market/price only when safe." -ForegroundColor Cyan
Write-Host ""


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

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    $away = ""
    $home = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $away = "$($parts[0])".Trim()
        $home = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $away = "$($parts[0])".Trim()
        $home = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $away) + " @ " + (Normalize-Team $home)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

$modelRows = Safe-Csv $modelCsv
$controlRows = Safe-Csv $controlCsv
$guardRows = Safe-Csv $guardCsv

$out = @()

foreach ($m in @($modelRows)) {
    $game = Get-Val $m @("Game")
    $pick = Get-Val $m @("Pick")

    $control = Find-By-Game $controlRows $game
    $guard = Find-By-Game $guardRows $game

    $market = ""
    $marketSource = ""
    $entry = ""

    if ($null -ne $control) {
        $controlPick = Get-Val $control @("Pick")
        if ((Normalize-Team $controlPick) -eq (Normalize-Team $pick)) {
            $market = Get-Val $control @("MarketProbability","Price")
            $entry = Get-Val $control @("Price")
            $marketSource = "CONTROL_BOARD_MATCHED_PICK"
        }
    }

    if ($market -eq "" -and $null -ne $guard) {
        $guardPick = Get-Val $guard @("Pick")
        if ((Normalize-Team $guardPick) -eq (Normalize-Team $pick)) {
            $entry = Get-Val $guard @("CurrentEntry","Entry")
            $market = $entry
            $marketSource = "PRICE_GUARD_MATCHED_PICK"
        }
    }

    $modelRaw = Num (Get-Val $m @("ModelProbabilityRaw"))
    $modelPct = Num (Get-Val $m @("ModelProbability"))
    if ($null -eq $modelRaw -and $null -ne $modelPct) { $modelRaw = $modelPct / 100.0 }

    $marketRaw = Num $market
    if ($null -ne $marketRaw -and $marketRaw -gt 1) { $marketRaw = $marketRaw / 100.0 }

    $edgePct = ""
    $decision = "NO_MARKET_YET"
    $reason = "No safe market price matched to model pick."

    if ($null -ne $modelRaw -and $null -ne $marketRaw -and $marketRaw -gt 0 -and $marketRaw -lt 1) {
        $edge = ($modelRaw - $marketRaw) * 100.0
        $edgePct = ([math]::Round($edge, 1)).ToString() + "%"
        $decision = "MODEL_MARKET_CONNECTED"
        $reason = "Model and market connected for same pick."
    }

    $out += ,[pscustomobject]@{
        Source = "ASTRODDS_266_SOURCE_MODEL_MARKET_BRIDGE"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $m @("GamePk")
        Game = $game
        Pick = $pick
        MlbStatus = Get-Val $m @("MlbStatus")
        ModelProbability = Get-Val $m @("ModelProbability")
        ModelProbabilityRaw = Get-Val $m @("ModelProbabilityRaw")
        SourceFirstConfidence = Get-Val $m @("SourceFirstConfidence")
        MarketProbability = if ($null -ne $marketRaw) { [math]::Round($marketRaw, 6) } else { "" }
        Entry = if ($entry -ne "") { $entry } else { $market }
        Edge = $edgePct
        BridgeDecision = $decision
        BridgeReason = $reason
        MarketSource = $marketSource
        ModelStatus = Get-Val $m @("ModelStatus")
        ModelType = Get-Val $m @("ModelType")
        AwayLineupStatus = Get-Val $m @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $m @("HomeLineupStatus")
        FullContextConnected = Get-Val $m @("FullContextConnected")
        ModelFlags = Get-Val $m @("ModelFlags")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connected = @($out | Where-Object { $_.BridgeDecision -eq "MODEL_MARKET_CONNECTED" }).Count
$noMarket = @($out | Where-Object { $_.BridgeDecision -ne "MODEL_MARKET_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 266 SOURCE MODEL + MARKET BRIDGE"
$lines += ""
$lines += "Rows checked: $($out.Count)"
$lines += "Model+market connected: $connected"
$lines += "No market yet: $noMarket"
$lines += ""
$lines += "BRIDGE BOARD"
foreach ($r in $out) {
    $lines += "- $($r.BridgeDecision) | $($r.Pick) | $($r.Game) | Model=$($r.ModelProbability) | Market=$($r.MarketProbability) | Edge=$($r.Edge) | Status=$($r.MlbStatus)"
    $lines += "  Reason=$($r.BridgeReason)"
}
$lines += ""
$lines += "IMPORTANT"
$lines += "- If market is missing, no official pick is allowed."
$lines += "- This does not invent prices."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rowsChecked = $out.Count
    modelMarketConnected = $connected
    noMarketYet = $noMarket
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
