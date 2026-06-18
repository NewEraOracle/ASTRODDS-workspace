$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$source = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"

$outTxt  = Join-Path $astro "ASTRODDS-telegram-official-message-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-telegram-official-message-latest.json"

Write-Host ""
Write-Host "ASTRODDS 211 TELEGRAM OFFICIAL MESSAGE BUILDER" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $source)) {
    Write-Host "WARNING: Locked official source missing:" -ForegroundColor Yellow
    Write-Host $source
    Write-Host "Run script 210 first."
    exit 0
}

try {
    $rows = @(Get-Content $source -Raw | ConvertFrom-Json)
} catch {
    Write-Host "WARNING: Cannot read locked JSON." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
    exit 0
}

if ($rows.Count -eq 0) {
    Write-Host "No official picks found. Telegram message not created." -ForegroundColor Yellow
    exit 0
}

function To-PctText($n) {
    if ($null -eq $n) { return "N/A" }
    try {
        $v = [double]$n
        if ($v -le 1) { $v = $v * 100 }
        return ("{0:N1}%" -f $v)
    } catch {
        return "N/A"
    }
}

function To-CentsText($n) {
    if ($null -eq $n) { return "N/A" }
    try {
        $v = [double]$n
        if ($v -le 1) { $v = $v * 100 }
        return ("{0:N1} cents" -f $v)
    } catch {
        return "N/A"
    }
}

$now = Get-Date -Format "yyyy-MM-dd HH:mm"

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("🚀 ASTRODDS OFFICIAL PICKS")
$lines.Add("MLB MONEYLINE ONLY")
$lines.Add("Generated: $now")
$lines.Add("")
$lines.Add("Rules:")
$lines.Add("• No parlay")
$lines.Add("• 5% bankroll max per pick")
$lines.Add("• Only official locked picks")
$lines.Add("• If the price moves too much, wait")
$lines.Add("")

$i = 1

foreach ($r in ($rows | Sort-Object EdgePct -Descending)) {
    $pick = "$($r.Pick)"
    $game = "$($r.Game)"
    $price = To-CentsText $r.Price
    $model = To-PctText $r.ModelProbability
    $edge = To-PctText $r.EdgePct
    $stake = if ($r.Stake) { "$($r.Stake)" } else { "5% bankroll" }
    $risk = if ($r.RiskLevel) { "$($r.RiskLevel)" } else { "medium" }

    $lines.Add("✅ OFFICIAL PICK #$i")
    $lines.Add("Pick: $pick")
    $lines.Add("Game: $game")
    $lines.Add("Market: Moneyline")
    $lines.Add("Entry price: $price")
    $lines.Add("Model: $model")
    $lines.Add("Edge: +$edge")
    $lines.Add("Stake: $stake")
    $lines.Add("Risk: $risk")
    $lines.Add("")

    $i++
}

$lines.Add("⚠️ Risk note:")
$lines.Add("These are data-driven picks, not guaranteed wins. We will lose some, but we only send spots where the model finds real value.")
$lines.Add("")
$lines.Add("ASTRODDS")

$message = $lines -join [Environment]::NewLine

$message | Set-Content -Encoding UTF8 $outTxt

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    source = $source
    officialCount = $rows.Count
    messageFile = $outTxt
    message = $message
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $outJson

Write-Host "TELEGRAM MESSAGE CREATED" -ForegroundColor Green
Write-Host ""
Write-Host $message
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
