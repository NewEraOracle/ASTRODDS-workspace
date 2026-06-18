$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$guardCsv = Join-Path $astro "ASTRODDS-249-price-guard-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-258-block-in-progress-new-drops-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-258-block-in-progress-new-drops-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-258-block-in-progress-new-drops-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-new-drops-only-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 258 BLOCK IN-PROGRESS NEW DROPS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - DO NOT SEND NEW PICKS AFTER START" -ForegroundColor Cyan
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
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) { return $n }
    return $null
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
        Key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
    }
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher"
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 }
    catch { return $null }
}

function Get-Game-Key($game) {
    return (Split-Game $game).Key
}

function Clean-KeyPart($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "\s+", " "
    return $x
}

$rows = Safe-Csv $guardCsv

$out = @()
foreach ($r in $rows) {
    $decision = Get-Val $r @("Decision")
    $status = (Get-Val $r @("Status")).ToLower()
    $final = $decision
    $reason = Get-Val $r @("Reason")

    if ($decision -eq "SEND_OK" -and ($status -match "in progress|live|final|game over|delayed")) {
        $final = "BLOCKED_ALREADY_STARTED"
        $reason = "Game is already $status. Do not send as a new client drop."
    }

    $out += ,[pscustomobject]@{
        FinalDropDecision = $final
        OriginalDecision = $decision
        Grade = Get-Val $r @("Grade")
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        Entry = Get-Val $r @("CurrentEntry")
        Confidence = Get-Val $r @("Confidence")
        Stake = Get-Val $r @("Stake")
        Status = Get-Val $r @("Status")
        Reason = $reason
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$send = @($out | Where-Object { $_.FinalDropDecision -eq "SEND_OK" })
$blocked = @($out | Where-Object { $_.FinalDropDecision -ne "SEND_OK" })

$telegram = @()
if ($send.Count -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• New drops only before first pitch"
    $telegram += "• Price guard passed"
    $telegram += "• 5% bankroll max per pick"
    $telegram += ""

    $i = 1
    foreach ($r in $send) {
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
    $telegram += "Confidence is not a guaranteed win rate."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS NEW CLIENT DROP BLOCKED"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "No new picks should be sent now."
    $telegram += ""
    foreach ($r in $blocked) {
        $telegram += "- $($r.Pick) | $($r.Game) | $($r.Status)"
        $telegram += "  Reason: $($r.Reason)"
    }
}

($telegram -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTelegram

$lines = @()
$lines += "ASTRODDS 258 BLOCK IN-PROGRESS NEW DROPS"
$lines += ""
$lines += "New-drop SEND_OK: $($send.Count)"
$lines += "Blocked: $($blocked.Count)"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.FinalDropDecision) | $($r.Pick) | $($r.Game) | Status=$($r.Status) | Confidence=$($r.Confidence)/100"
    $lines += "  Reason=$($r.Reason)"
}
$lines += ""
$lines += "TELEGRAM"
$lines += $outTelegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    sendOk = $send.Count
    blocked = $blocked.Count
    telegram = $outTelegram
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram: $outTelegram"
Write-Host ""
