$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$source = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"

$outTxt  = Join-Path $astro "ASTRODDS-telegram-official-message-v2-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-telegram-official-message-v2-latest.json"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 212 TELEGRAM OFFICIAL MESSAGE V2" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLEAN PUBLIC DROP" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $source)) {
    Write-Host "WARNING: Locked official source missing:" -ForegroundColor Yellow
    Write-Host $source
    Write-Host "Run 210 first."
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
    Write-Host "No official picks found. Message not created." -ForegroundColor Yellow
    exit 0
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }

    $n = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }

    return $null
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "¢"
}

function MaxEntry($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }

    # Max entry = current price + 2 cents.
    # Example: 56.9¢ current = max buy around 58.9¢.
    if ($n -le 1) {
        $n = ($n + 0.02) * 100
    } else {
        $n = $n + 2
    }

    if ($n -gt 99) { $n = 99 }

    return $n.ToString("0.0", $culture) + "¢"
}

$now = Get-Date -Format "yyyy-MM-dd HH:mm"

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("🚀 ASTRODDS OFFICIAL PICKS")
$lines.Add("MLB MONEYLINE ONLY")
$lines.Add("Generated: $now")
$lines.Add("")
$lines.Add("Simple rules:")
$lines.Add("• No parlays")
$lines.Add("• 5% bankroll max per pick")
$lines.Add("• Buy only near the entry price")
$lines.Add("• If price is above max entry, wait")
$lines.Add("")

$i = 1

foreach ($r in ($rows | Sort-Object EdgePct -Descending)) {
    $pick = "$($r.Pick)"
    $game = "$($r.Game)"
    $entry = Cents $r.Price
    $max = MaxEntry $r.Price
    $model = Pct $r.ModelProbability
    $edge = Pct $r.EdgePct
    $stake = if ($r.Stake) { "$($r.Stake)" } else { "5% bankroll" }
    $risk = if ($r.RiskLevel) { "$($r.RiskLevel)" } else { "medium" }

    $lines.Add("✅ OFFICIAL BUY #$i")
    $lines.Add("$pick ML")
    $lines.Add("Game: $game")
    $lines.Add("Entry: $entry")
    $lines.Add("Max entry: $max")
    $lines.Add("Model: $model")
    $lines.Add("Edge: +$edge")
    $lines.Add("Stake: $stake")
    $lines.Add("Risk: $risk")
    $lines.Add("")

    $i++
}

$lines.Add("⚠️ Risk note:")
$lines.Add("These are value spots, not guaranteed wins. We keep it simple: official picks only, no parlays, controlled stake.")
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
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

Write-Host "TELEGRAM V2 MESSAGE CREATED" -ForegroundColor Green
Write-Host ""
Write-Host $message
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
