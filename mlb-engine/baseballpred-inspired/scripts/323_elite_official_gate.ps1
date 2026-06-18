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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        return (Normalize-Team $parts[0]) + " @ " + (Normalize-Team $parts[1])
    }
    return (Normalize-Team $g)
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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$lineGateCsv = Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.csv"
$eliteCsv = Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.json"

Write-Host ""
Write-Host "ASTRODDS 323B ELITE OFFICIAL GATE - CLEAN CLASSIFICATION" -ForegroundColor Cyan
Write-Host "Fix: negative/no-value rows are BLOCKED, not REVIEW." -ForegroundColor Cyan
Write-Host ""

$gate = Safe-Csv $lineGateCsv
$elite = Safe-Csv $eliteCsv
$out = @()

foreach ($r in $gate) {
    $game = Get-Val $r @("Game")
    $e = Find-By-Game $elite $game

    $lineDecision = Get-Val $r @("FinalDecision")
    $lineHard = Get-Val $r @("HardBlocks")
    $edge = Num (Get-Val $r @("EdgeVsBest"))
    $status = Get-Val $r @("MlbStatus")
    $eliteStatus = Get-Val $e @("EliteContextStatus")

    $hard = @()
    $warn = @()
    $reasonClass = "UNKNOWN"

    if ($lineDecision -ne "CLIENT_OFFICIAL_LINE_SHOP_SEND_OK") {
        $hard += "line-shopping gate not SEND_OK"

        if ($status -match "In Progress|Final|Game Over|Delayed|Suspended") {
            $reasonClass = "BLOCKED_NOT_LIVE_SAFE"
        } elseif ($null -ne $edge -and $edge -lt 3) {
            $reasonClass = "BLOCKED_NO_VALUE"
        } elseif ($null -ne $edge -and $edge -ge 3 -and $edge -lt 5) {
            $reasonClass = "REVIEW_ONLY_EDGE_3_TO_5"
        } else {
            $reasonClass = "BLOCKED_CONTEXT_OR_MARKET"
        }
    }

    if ($eliteStatus -eq "ELITE_CONTEXT_MISSING_CORE") {
        $hard += "elite core context missing"
        if ($reasonClass -eq "UNKNOWN") { $reasonClass = "BLOCKED_ELITE_CORE_MISSING" }
    }

    if ($eliteStatus -eq "ELITE_CONTEXT_PARTIAL_PREMIUM_WARNINGS") {
        $warn += "premium context warnings: $((Get-Val $e @('PremiumWarnings')))"
    }

    $final = "BLOCKED_FOR_REVIEW"

    if ($lineDecision -eq "CLIENT_OFFICIAL_LINE_SHOP_SEND_OK" -and $eliteStatus -ne "ELITE_CONTEXT_MISSING_CORE") {
        $final = "CLIENT_OFFICIAL_ELITE_SEND_OK"
        $reasonClass = "SEND_OK"
    } elseif ($reasonClass -eq "REVIEW_ONLY_EDGE_3_TO_5") {
        $final = "REVIEW_ONLY_ELITE"
    } elseif ($reasonClass -eq "BLOCKED_NO_VALUE") {
        $final = "BLOCKED_NO_VALUE"
    } elseif ($reasonClass -eq "BLOCKED_NOT_LIVE_SAFE") {
        $final = "BLOCKED_NOT_LIVE_SAFE"
    } elseif ($reasonClass -eq "BLOCKED_ELITE_CORE_MISSING") {
        $final = "BLOCKED_ELITE_CORE_MISSING"
    } else {
        $final = "BLOCKED_FOR_REVIEW"
    }

    $out += ,[pscustomobject]@{
        FinalEliteDecision = $final
        ReasonClass = $reasonClass
        Pick = Get-Val $r @("Pick")
        Game = $game
        MlbStatus = $status
        ModelProbability = Get-Val $r @("ModelProbability")
        BestEntry = Get-Val $r @("BestEntry")
        BestBook = Get-Val $r @("BestBook")
        EdgeVsBest = Get-Val $r @("EdgeVsBest")
        EliteContextStatus = $eliteStatus
        LineShopDecision = $lineDecision
        AwayStarter = Get-Val $e @("AwayStarter")
        HomeStarter = Get-Val $e @("HomeStarter")
        AwayFIPProxy = Get-Val $e @("AwayFIPProxy")
        HomeFIPProxy = Get-Val $e @("HomeFIPProxy")
        AwayReliefStressLevel = Get-Val $e @("AwayReliefStressLevel")
        HomeReliefStressLevel = Get-Val $e @("HomeReliefStressLevel")
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$send = @($out | Where-Object { $_.FinalEliteDecision -eq "CLIENT_OFFICIAL_ELITE_SEND_OK" }).Count
$review = @($out | Where-Object { $_.FinalEliteDecision -eq "REVIEW_ONLY_ELITE" }).Count
$noValue = @($out | Where-Object { $_.FinalEliteDecision -eq "BLOCKED_NO_VALUE" }).Count
$notLive = @($out | Where-Object { $_.FinalEliteDecision -eq "BLOCKED_NOT_LIVE_SAFE" }).Count
$blockedOther = @($out | Where-Object { $_.FinalEliteDecision -like "BLOCKED*" -and $_.FinalEliteDecision -ne "BLOCKED_NO_VALUE" -and $_.FinalEliteDecision -ne "BLOCKED_NOT_LIVE_SAFE" }).Count

$lines = @()
$lines += "ASTRODDS 323B ELITE OFFICIAL GATE - CLEAN CLASSIFICATION"
$lines += ""
$lines += "SEND_OK: $send"
$lines += "REVIEW: $review"
$lines += "BLOCKED_NO_VALUE: $noValue"
$lines += "BLOCKED_NOT_LIVE_SAFE: $notLive"
$lines += "BLOCKED_OTHER: $blockedOther"
$lines += "Rows: $($out.Count)"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.FinalEliteDecision) | $($r.Pick) | $($r.Game) | status=$($r.MlbStatus) | edge=$($r.EdgeVsBest) | elite=$($r.EliteContextStatus)"
    if ($r.HardBlocks -ne "") { $lines += "  Hard=$($r.HardBlocks)" }
    if ($r.Warnings -ne "") { $lines += "  Warn=$($r.Warnings)" }
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    sendOk=$send
    review=$review
    blockedNoValue=$noValue
    blockedNotLiveSafe=$notLive
    blockedOther=$blockedOther
    rows=$out.Count
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
