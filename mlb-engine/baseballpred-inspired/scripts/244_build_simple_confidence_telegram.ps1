$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$gate240 = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"

$outTxt = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.json"
$outCsv = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.csv"

Write-Host ""
Write-Host "ASTRODDS 244 SIMPLE CONFIDENCE TELEGRAM MESSAGE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLIENT DISPLAY CONFIDENCE /100" -ForegroundColor Cyan
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

function Num($v) {
    if ($null -eq $v) { return $null }

    $s = "$v".Trim()
    if ($s -eq "") { return $null }

    $s = $s.Replace("%","")
    $s = $s.Replace("¢","")
    $s = $s.Replace(",", ".")

    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture

    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }

    return $null
}

function Edge-Grade($edgeText) {
    $edge = Num $edgeText

    if ($null -eq $edge) { return "OFFICIAL" }
    if ($edge -ge 10) { return "STRONG BUY" }
    if ($edge -ge 5) { return "VALUE BUY" }

    return "OFFICIAL"
}

function Stake-Text($grade) {
    if ($grade -eq "STRONG BUY") {
        return "5% bankroll max"
    }

    if ($grade -eq "VALUE BUY") {
        return "2–3% bankroll recommended / 5% max"
    }

    return "1–2% bankroll recommended"
}

function Confidence-Score($row) {
    $edge = Num (Get-Val $row @("Edge"))
    $model = Num (Get-Val $row @("ModelProbability"))
    $awayLineup = Get-Val $row @("AwayLineupStatus")
    $homeLineup = Get-Val $row @("HomeLineupStatus")
    $status = Get-Val $row @("MlbStatus")
    $reason = Get-Val $row @("FinalReason")

    if ($null -eq $edge) { $edge = 0 }
    if ($null -eq $model) { $model = 50 }

    # Convert model if needed
    if ($model -le 1) { $model = $model * 100 }

    # Internal confidence score, NOT win probability.
    $score = 45.0

    # Edge contribution
    $edgeBonus = [math]::Min(25.0, [math]::Max(0.0, $edge * 1.5))
    $score += $edgeBonus

    # Model strength contribution
    $modelBonus = [math]::Min(12.0, [math]::Max(0.0, ($model - 50.0) * 0.8))
    $score += $modelBonus

    # Live lineup contribution
    if ($awayLineup -eq "confirmed" -and $homeLineup -eq "confirmed") {
        $score += 8.0
    }

    # Game status contribution
    $s = "$status".ToLower()
    if ($s -match "pre-game|pregame|warmup|in progress|live") {
        $score += 3.0
    }

    # Source/gate contribution
    if ("$reason" -match "Passed|trusted full slate|Promoted") {
        $score += 5.0
    }

    # Cap confidence so VALUE BUY does not look like a lock.
    if ($edge -lt 10) {
        $score = [math]::Min($score, 84.0)
    } else {
        $score = [math]::Min($score, 92.0)
    }

    $score = [math]::Max(55.0, $score)

    return [int][math]::Round($score, 0)
}

$rows = Safe-Csv $gate240

$officialRows = @($rows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$displayRows = @()

foreach ($r in $officialRows) {
    $grade = Edge-Grade (Get-Val $r @("Edge"))
    $confidence = Confidence-Score $r

    $displayRows += ,[pscustomobject]@{
        Grade = $grade
        Confidence = $confidence
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        Entry = Get-Val $r @("Price")
        Stake = Stake-Text $grade
        Status = Get-Val $r @("MlbStatus")
        InternalModel = Get-Val $r @("ModelProbability")
        InternalEdge = Get-Val $r @("Edge")
        InternalReason = Get-Val $r @("FinalReason")
    }
}

$displayRows = @($displayRows | Sort-Object Confidence -Descending)

$telegram = @()

if ($displayRows.Count -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• Confidence is an internal ASTRODDS score /100"
    $telegram += "• 5% bankroll max per pick"
    $telegram += "• Blocked/review picks are not sent"
    $telegram += ""

    $i = 1

    foreach ($r in $displayRows) {
        $telegram += "✅ $($r.Grade) #$i"
        $telegram += "$($r.Pick) ML"
        $telegram += "Game: $($r.Game)"
        $telegram += "Entry: $($r.Entry)"
        $telegram += "Confidence: $($r.Confidence)/100"
        $telegram += "Stake: $($r.Stake)"
        $telegram += "Status: $($r.Status)"
        $telegram += ""
        $i++
    }

    $telegram += "⚠️ Risk note:"
    $telegram += "Confidence is not a guaranteed win rate. It is a simplified score based on ASTRODDS internal model, market value, live lineups, and safety gates."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegram += "No official picks passed the final confidence gate."
}

$telegramText = $telegram -join [Environment]::NewLine
$telegramText | Set-Content -Encoding UTF8 $outTxt
$displayRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialPicks = $displayRows.Count
    telegramFile = $outTxt
    rows = @($displayRows)
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

Write-Host ""
Write-Host $telegramText
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
