$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$script243 = Join-Path $scripts "243_run_final_edge_tiered_officials.ps1"
$script244 = Join-Path $scripts "244_build_simple_confidence_telegram.ps1"

$outTxt = Join-Path $astro "ASTRODDS-final-confidence-client-drop-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-final-confidence-client-drop-run-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-final-confidence-client-drop-child-log-latest.txt"
$clientMessage = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 245 FINAL CONFIDENCE CLIENT DROP RUNNER" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FINAL CLIENT MESSAGE" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{
            Name = $name
            Status = "MISSING"
            ExitCode = ""
            DurationSec = 0
        }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{
                Name = $name
                Status = "OK"
                ExitCode = "0"
                DurationSec = $duration
            }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{
                Name = $name
                Status = "ERROR"
                ExitCode = "$exitCode"
                DurationSec = $duration
            }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"

        Write-Host "ERROR: $name" -ForegroundColor Red
        Write-Host $_.Exception.Message

        return [pscustomobject]@{
            Name = $name
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
    }
}

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

$steps = @()
$steps += ,(Run-Step "243 final edge-tiered official runner" $script243)
$steps += ,(Run-Step "244 simple confidence client message" $script244)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$messageText = ""
if (Test-Path $clientMessage) {
    $messageText = Get-Content $clientMessage -Raw
}

$confidenceCsv = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.csv"
$confidenceRows = Safe-Csv $confidenceCsv

$officialCount = $confidenceRows.Count
$strongCount = @($confidenceRows | Where-Object { (Get-Val $_ @("Grade")) -eq "STRONG BUY" }).Count
$valueCount = @($confidenceRows | Where-Object { (Get-Val $_ @("Grade")) -eq "VALUE BUY" }).Count

$lines = @()
$lines += "ASTRODDS 245 FINAL CONFIDENCE CLIENT DROP RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Official client picks: $officialCount"
$lines += "Strong Buy: $strongCount"
$lines += "Value Buy: $valueCount"
$lines += ""

$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""

$lines += "CLIENT MESSAGE FILE"
$lines += $clientMessage
$lines += ""

$lines += "FINAL CLIENT MESSAGE"
$lines += $messageText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialClientPicks = $officialCount
    strongBuy = $strongCount
    valueBuy = $valueCount
    clientMessageFile = $clientMessage
    childLog = $outChildLog
    steps = @($steps)
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Client message: $clientMessage"
Write-Host ""
