$ErrorActionPreference = "Continue"


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
    $awayTeamName = ""
    $homeTeamName = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
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

function Avg($arr) {
    $vals = @()
    foreach ($x in @($arr)) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro
Load-EnvLocal $root

$outTxt = Join-Path $astro "ASTRODDS-297-telegram-auto-send-safe-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-297-telegram-auto-send-safe-latest.json"
$sentCsv = Join-Path $astro "ASTRODDS-telegram-sent-ledger-latest.csv"
$msgPath = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 297 TELEGRAM AUTO-SEND SAFE" -ForegroundColor Cyan
Write-Host "Default is dry-run unless ASTRODDS_TELEGRAM_SEND=YES." -ForegroundColor Cyan
Write-Host ""

$message = ""
if (Test-Path $msgPath) { $message = Get-Content $msgPath -Raw }

$sendAllowed = ($env:ASTRODDS_TELEGRAM_SEND -eq "YES")
$token = $env:TELEGRAM_BOT_TOKEN
if (-not $token) { $token = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
$chatId = $env:TELEGRAM_CHAT_ID
if (-not $chatId) { $chatId = $env:ASTRODDS_TELEGRAM_CHAT_ID }

$eligible = $false
if ($message -match "ASTRODDS OFFICIAL PICKS" -and $message -notmatch "NEW CLIENT DROP BLOCKED") { $eligible = $true }

$fingerprint = [System.BitConverter]::ToString((New-Object Security.Cryptography.SHA256Managed).ComputeHash([Text.Encoding]::UTF8.GetBytes($message))).Replace("-","")
$sent = Safe-Csv $sentCsv
$alreadySent = @($sent | Where-Object { (Get-Val $_ @("Fingerprint")) -eq $fingerprint }).Count -gt 0

$status = "DRY_RUN"
$reason = ""
if (-not $eligible) { $status = "NOT_ELIGIBLE"; $reason = "message is blocked/no official picks" }
elseif ($alreadySent) { $status = "ALREADY_SENT"; $reason = "same message fingerprint already sent" }
elseif (-not $sendAllowed) { $status = "DRY_RUN"; $reason = "set ASTRODDS_TELEGRAM_SEND=YES to send" }
elseif (-not $token -or -not $chatId) { $status = "MISSING_TELEGRAM_ENV"; $reason = "missing TELEGRAM_BOT_TOKEN/CHAT_ID" }
else {
    try {
        $url = "https://api.telegram.org/bot$token/sendMessage"
        $body = @{ chat_id=$chatId; text=$message }
        Invoke-RestMethod -Uri $url -Method Post -Body $body -TimeoutSec 20 | Out-Null
        $status = "SENT"
        $reason = "sent to Telegram"
        $sent += ,[pscustomobject]@{ SentAt=(Get-Date).ToString("o"); Fingerprint=$fingerprint; MessageFile=$msgPath }
        $sent | Export-Csv -NoTypeInformation -Encoding UTF8 $sentCsv
    } catch {
        $status = "SEND_ERROR"
        $reason = $_.Exception.Message
    }
}

$lines = @()
$lines += "ASTRODDS 297 TELEGRAM AUTO-SEND SAFE"
$lines += ""
$lines += "Status: $status"
$lines += "Reason: $reason"
$lines += "Eligible: $eligible"
$lines += "Already sent: $alreadySent"
$lines += "Send env enabled: $sendAllowed"
$lines += "Message file: $msgPath"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    reason=$reason
    eligible=$eligible
    alreadySent=$alreadySent
    sendEnvEnabled=$sendAllowed
    messageFile=$msgPath
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
