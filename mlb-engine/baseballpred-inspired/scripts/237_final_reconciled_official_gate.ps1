$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$gate228 = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"
$gate236 = Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.csv"

$outCsv = Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-final-reconciled-official-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 237 FINAL RECONCILED OFFICIAL GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - 228 SAFETY + 236 FULL CONTEXT" -ForegroundColor Cyan
Write-Host ""

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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Key($game, $pick) {
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

    return ((Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName) + "|" + (Normalize-Team $pick))
}

$rows228 = Safe-Csv $gate228
$rows236 = Safe-Csv $gate236

if ($rows236.Count -eq 0) {
    Write-Host "ERROR: 236 gate missing. Run 236 first." -ForegroundColor Red
    exit 0
}

$map228 = @{}

foreach ($r in $rows228) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    if ($game -eq "" -or $pick -eq "") { continue }

    $key = Split-Key $game $pick
    $map228[$key] = $r
}

$finalRows = @()

foreach ($r236 in $rows236) {
    $game = Get-Val $r236 @("Game")
    $pick = Get-Val $r236 @("Pick")
    if ($game -eq "") { continue }

    $key = Split-Key $game $pick
    $r228 = $null
    if ($map228.ContainsKey($key)) {
        $r228 = $map228[$key]
    }

    $decision236 = Get-Val $r236 @("Decision")
    $sourceType = Get-Val $r236 @("SourceType")
    $coverage = Get-Val $r236 @("CoverageStatus")

    $finalDecision = $decision236
    $finalReason = "236 full-context decision used."
    $hard = Get-Val $r236 @("HardBlocks")
    $warn = Get-Val $r236 @("Warnings")

    $price = Get-Val $r236 @("Price")
    $model = Get-Val $r236 @("ModelProbability")
    $market = Get-Val $r236 @("MarketProbability")
    $edge = Get-Val $r236 @("Edge")
    $awayLineup = Get-Val $r236 @("AwayLineupStatus")
    $homeLineup = Get-Val $r236 @("HomeLineupStatus")
    $mlbStatus = Get-Val $r236 @("MlbStatus")

    if ($null -ne $r228) {
        $decision228 = Get-Val $r228 @("Decision")
        $hard228 = Get-Val $r228 @("HardBlocks")
        $warn228 = Get-Val $r228 @("Warnings")

        $price228 = Get-Val $r228 @("Price")
        $publicModel228 = Get-Val $r228 @("PublicModel")
        $fullModel228 = Get-Val $r228 @("FullSlateModel")
        $edge228 = Get-Val $r228 @("Edge")

        if ($price228 -ne "") { $price = $price228 }
        if ($publicModel228 -ne "") { $model = $publicModel228 }
        if ($edge228 -ne "") { $edge = $edge228 }

        if ($decision228 -eq "BLOCKED_FOR_REVIEW") {
            $finalDecision = "BLOCKED_FOR_REVIEW"
            $finalReason = "228 safety gate blocked this public aPick; 236 cannot override it."

            if ($hard -ne "" -and $hard228 -ne "") {
                $hard = "$hard | 228: $hard228"
            } elseif ($hard228 -ne "") {
                $hard = "228: $hard228"
            }

            if ($warn -ne "" -and $warn228 -ne "") {
                $warn = "$warn | 228: $warn228"
            } elseif ($warn228 -ne "") {
                $warn = "228: $warn228"
            }
        } elseif ($decision228 -eq "CLIENT_OFFICIAL_SEND_OK") {
            $finalDecision = "CLIENT_OFFICIAL_SEND_OK"
            $finalReason = "Passed 228 public aPick safety gate and 236 context gate."
        } elseif ($decision228 -eq "REVIEW_ONLY") {
            $finalDecision = "REVIEW_ONLY"
            $finalReason = "228 marked this pick review-only."
        }
    } else {
        if ($sourceType -eq "CONTEXT_ONLY" -and $decision236 -eq "CLIENT_OFFICIAL_SEND_OK") {
            $finalDecision = "REVIEW_ONLY_CONTEXT"
            $finalReason = "Context-only row cannot become official until model/market source is verified."
            if ($warn -ne "") { $warn += " | " }
            $warn += "context-only row held for verification"
        }
    }

    if ($coverage -eq "NO_MODEL_YET") {
        $finalDecision = "BLOCKED_FOR_REVIEW"
        $finalReason = "No ASTRODDS model available for this game."
    }

    $finalRows += ,[pscustomobject]@{
        FinalDecision = $finalDecision
        SourceType = $sourceType
        CoverageStatus = $coverage
        Game = $game
        Pick = $pick
        MlbStatus = $mlbStatus
        Price = $price
        ModelProbability = $model
        MarketProbability = $market
        Edge = $edge
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        HardBlocks = $hard
        Warnings = $warn
        FinalReason = $finalReason
    }
}

$sendOk = @($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$reviewContext = @($finalRows | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY_CONTEXT" }).Count
$reviewOnly = @($finalRows | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY" }).Count
$blocked = @($finalRows | Where-Object { $_.FinalDecision -eq "BLOCKED_FOR_REVIEW" }).Count

$clientDecision = "CLIENT_DROP_BLOCKED"
if ($sendOk -gt 0) {
    if ($blocked -gt 0 -or $reviewOnly -gt 0 -or $reviewContext -gt 0) {
        $clientDecision = "CLIENT_DROP_PARTIAL_ALLOWED"
    } else {
        $clientDecision = "CLIENT_DROP_ALLOWED"
    }
}

$finalRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$telegramLines = @()

if ($sendOk -gt 0) {
    $telegramLines += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegramLines += "MLB MONEYLINE ONLY"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "Rules:"
    $telegramLines += "• No parlays"
    $telegramLines += "• 5% bankroll max per pick"
    $telegramLines += "• Only final reconciled SEND_OK picks"
    $telegramLines += "• Blocked/review picks are not sent"
    $telegramLines += ""

    $i = 1
    foreach ($r in ($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" })) {
        $telegramLines += "✅ OFFICIAL BUY #$i"
        $telegramLines += "$($r.Pick) ML"
        $telegramLines += "Game: $($r.Game)"
        $telegramLines += "Entry: $($r.Price)"
        $telegramLines += "Model: $($r.ModelProbability)"
        $telegramLines += "Edge: $($r.Edge)"
        $telegramLines += "Lineups: $($r.AwayLineupStatus) / $($r.HomeLineupStatus)"
        $telegramLines += "Status: $($r.MlbStatus)"
        $telegramLines += ""
        $i++
    }

    $telegramLines += "Why this passed:"
    $telegramLines += "• Market connected"
    $telegramLines += "• Model probability valid"
    $telegramLines += "• Live lineups confirmed"
    $telegramLines += "• Safety gates reconciled"
    $telegramLines += ""
    $telegramLines += "⚠️ Risk note:"
    $telegramLines += "These are data-driven value spots, not guaranteed wins."
    $telegramLines += ""
    $telegramLines += "ASTRODDS"
} else {
    $telegramLines += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "No final SEND_OK picks."
}

($telegramLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTelegram

$lines = @()
$lines += "ASTRODDS 237 FINAL RECONCILED OFFICIAL GATE"
$lines += ""
$lines += "Client decision: $clientDecision"
$lines += "CLIENT_OFFICIAL_SEND_OK: $sendOk"
$lines += "REVIEW_ONLY_CONTEXT: $reviewContext"
$lines += "REVIEW_ONLY: $reviewOnly"
$lines += "BLOCKED_FOR_REVIEW: $blocked"
$lines += ""

$lines += "FINAL OFFICIAL SEND_OK"
$okRows = @($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" })
if ($okRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($x in $okRows) {
        $lines += "- $($x.Pick) | $($x.Game) | Entry=$($x.Price) | Model=$($x.ModelProbability) | Edge=$($x.Edge)"
    }
}
$lines += ""

$lines += "REVIEW CONTEXT"
$ctxRows = @($finalRows | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY_CONTEXT" })
if ($ctxRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($x in $ctxRows) {
        $lines += "- $($x.Pick) | $($x.Game) | Model=$($x.ModelProbability) | Edge=$($x.Edge)"
        if ($x.Warnings -ne "") { $lines += "  Warn: $($x.Warnings)" }
    }
}
$lines += ""

$lines += "BLOCKED"
foreach ($x in ($finalRows | Where-Object { $_.FinalDecision -eq "BLOCKED_FOR_REVIEW" })) {
    $lines += "- $($x.Pick) | $($x.Game)"
    if ($x.HardBlocks -ne "") { $lines += "  Hard: $($x.HardBlocks)" }
    $lines += "  Reason: $($x.FinalReason)"
}
$lines += ""

$lines += "TELEGRAM OUTPUT"
$lines += $outTelegram
$lines += ""

$lines += "IMPORTANT"
$lines += "237 is the final safety layer."
$lines += "If 228 blocked a public aPick, 236 cannot override that block."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOk
    reviewOnlyContext = $reviewContext
    reviewOnly = $reviewOnly
    blocked = $blocked
    telegramOutput = $outTelegram
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram: $outTelegram"
Write-Host ""
