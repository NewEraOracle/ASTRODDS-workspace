$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$rankerFile = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$publicBoard = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$clientSafeCsv = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.csv"

$outJson = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.json"
$outCsv  = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.csv"
$outTxt  = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.txt"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 220 REPAIR RANKER MODEL PROBABILITY" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLIENT SAFE RANKER COPY" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }
    if ($data -is [System.Array]) { return @($data) }

    $props = @($data.PSObject.Properties)
    $arrayProps = @($props | Where-Object {
        ($_.Value -is [System.Array]) -or (($_.Value -is [System.Collections.IEnumerable]) -and !($_.Value -is [string]))
    })

    if ($arrayProps.Count -gt 0) {
        $max = 0
        foreach ($p in $arrayProps) {
            $count = @($p.Value).Count
            if ($count -gt $max) { $max = $count }
        }

        if ($max -gt 1) {
            $rows = @()
            for ($i = 0; $i -lt $max; $i++) {
                $h = [ordered]@{}
                foreach ($p in $props) {
                    $v = $p.Value
                    if (($v -is [System.Array]) -or (($v -is [System.Collections.IEnumerable]) -and !($v -is [string]))) {
                        $arr = @($v)
                        if ($i -lt $arr.Count) { $h[$p.Name] = $arr[$i] }
                        else { $h[$p.Name] = "" }
                    } else {
                        $h[$p.Name] = $v
                    }
                }
                $rows += ,([pscustomobject]$h)
            }
            return @($rows)
        }
    }

    return @($data)
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace(",", ".")
    $n = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }
    return $null
}

function Is-Prob($v) {
    $n = Num $v
    return ($null -ne $n -and $n -gt 0 -and $n -lt 1)
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

function Get-Prop($obj, $name) {
    if ($null -eq $obj) { return "" }
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return "" }
    if ($null -eq $p.Value) { return "" }
    return "$($p.Value)".Trim()
}

function FirstNonEmpty($obj, $names) {
    foreach ($n in @($names)) {
        $v = Get-Prop $obj $n
        if ($v -ne "") { return $v }
    }
    return ""
}

function Is-TrueText($v) {
    $s = "$v".Trim().ToLower()
    return ($s -eq "true" -or $s -eq "1" -or $s -eq "yes")
}

$ranker = Read-JsonSafe $rankerFile
$public = Read-JsonSafe $publicBoard

if ($null -eq $ranker -or $null -eq $ranker.gameBoard) {
    Write-Host "ERROR: Ranker file missing or invalid." -ForegroundColor Red
    Write-Host $rankerFile
    exit 0
}

$rankerRows = @(Normalize-Rows $ranker.gameBoard)

$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$fullSlateRows = @()
if (Test-Path $fullSlate) {
    try { $fullSlateRows = @(Import-Csv $fullSlate) }
    catch { $fullSlateRows = @() }
}

$clientSafeRows = @()
if (Test-Path $clientSafeCsv) {
    try { $clientSafeRows = @(Import-Csv $clientSafeCsv) }
    catch { $clientSafeRows = @() }
}

$safeRows = @()
$fixedModelCount = 0
$blockedOfficialCount = 0
$reviewOnlyCount = 0
$sendOkCount = 0

foreach ($r in $rankerRows) {
    $game = FirstNonEmpty $r @("game", "Game")
    $pick = FirstNonEmpty $r @("pick", "Pick")

    $publicPick = $publicAPicks | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    $slate = $fullSlateRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $slate) {
        $slate = $fullSlateRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $safeGate = $clientSafeRows | Where-Object {
        "$($_.Game)".Trim() -eq $game -and "$($_.Pick)".Trim() -eq $pick
    } | Select-Object -First 1

    $rankModel = Num (FirstNonEmpty $r @("modelProbability", "ModelProbability"))
    $publicModel = Num (FirstNonEmpty $publicPick @("model", "modelProbability", "ModelProbability"))
    $fullModel = Num (FirstNonEmpty $slate @("modelProbability", "ModelProbability"))

    $modelSource = "ranker_existing"
    $finalModel = $rankModel

    if ($null -eq $finalModel -and $null -ne $publicModel -and $publicModel -gt 0 -and $publicModel -lt 1) {
        $finalModel = $publicModel
        $modelSource = "public_board_model"
        $fixedModelCount++
    } elseif ($null -eq $finalModel -and $null -ne $fullModel -and $fullModel -gt 0 -and $fullModel -lt 1) {
        $finalModel = $fullModel
        $modelSource = "full_slate_model"
        $fixedModelCount++
    }

    $hard = @()
    $warn = @()

    if ($pick -eq "" -or $game -eq "") {
        $hard += "missing game or pick"
    }

    if ($null -eq $finalModel -or $finalModel -le 0 -or $finalModel -ge 1) {
        $hard += "modelProbability still missing or invalid"
    }

    if ($null -ne $slate) {
        if (Is-TrueText "$($slate.paperOnly)") {
            $hard += "full slate paperOnly=True"
        }

        if ("$($slate.awayLineupStatus)" -eq "missing" -or "$($slate.homeLineupStatus)" -eq "missing") {
            $warn += "lineups missing"
        }
    }

    if ($null -ne $publicModel -and $null -ne $fullModel) {
        $diff = [math]::Abs($publicModel - $fullModel)
        if ($diff -gt 0.05) {
            $hard += "public/fullSlate model mismatch above 5%"
        }
    }

    if ($null -ne $safeGate) {
        if ("$($safeGate.Decision)" -eq "BLOCKED_FOR_REVIEW") {
            $hard += "client-safe gate blocked this pick"
        } elseif ("$($safeGate.Decision)" -eq "REVIEW_ONLY") {
            $warn += "client-safe gate review only"
        }
    }

    $finalDecision = "CLIENT_OFFICIAL_SEND_OK"
    $finalStatus = "OFFICIAL"
    $telegram = $true

    if ($hard.Count -gt 0) {
        $finalDecision = "BLOCKED_FOR_REVIEW"
        $finalStatus = "BLOCKED_FOR_REVIEW"
        $telegram = $false
        $blockedOfficialCount++
    } elseif ($warn.Count -gt 0) {
        $finalDecision = "REVIEW_ONLY"
        $finalStatus = "REVIEW_ONLY"
        $telegram = $false
        $reviewOnlyCount++
    } else {
        $sendOkCount++
    }

    $safeRows += ,[pscustomobject]@{
        rank = FirstNonEmpty $r @("rank", "Rank")
        status = $finalStatus
        clientSafeDecision = $finalDecision
        game = $game
        awayTeam = FirstNonEmpty $r @("awayTeam", "AwayTeam")
        homeTeam = FirstNonEmpty $r @("homeTeam", "HomeTeam")
        pick = $pick
        marketType = FirstNonEmpty $r @("marketType", "MarketType")
        line = FirstNonEmpty $r @("line", "Line")
        price = FirstNonEmpty $r @("price", "Price")
        modelProbability = if ($null -ne $finalModel) { $finalModel.ToString("0.######", $culture) } else { "" }
        modelProbabilityText = Pct $finalModel
        modelProbabilitySource = $modelSource
        fullSlateModelProbability = if ($null -ne $fullModel) { $fullModel.ToString("0.######", $culture) } else { "" }
        edgePct = FirstNonEmpty $r @("edgePct", "EdgePct", "edge")
        baseballPredScore = FirstNonEmpty $r @("baseballPredScore", "BaseballPredScore")
        grade = FirstNonEmpty $r @("grade", "Grade")
        telegramEligible = $telegram
        paperOnly = if ($finalStatus -eq "OFFICIAL") { $false } else { $true }
        mainReason = FirstNonEmpty $r @("mainReason", "MainReason")
        riskReason = FirstNonEmpty $r @("riskReason", "RiskReason")
        hardBlocks = ($hard -join " | ")
        warnings = ($warn -join " | ")
    }
}

$out = [ordered]@{
    generatedAt = (Get-Date).ToString("o")
    sourceRanker = $rankerFile
    rows = $safeRows.Count
    sendOk = $sendOkCount
    reviewOnly = $reviewOnlyCount
    blocked = $blockedOfficialCount
    fixedModelProbabilityRows = $fixedModelCount
    gameBoard = @($safeRows)
    rule = "Client-safe ranker copy. OFFICIAL impossible when paperOnly=True, modelProbability missing, client gate blocked, model mismatch >5%, or lineups missing."
}

$lines = @()
$lines += "ASTRODDS 220 REPAIR RANKER MODEL PROBABILITY"
$lines += ""
$lines += "Rows processed: $($safeRows.Count)"
$lines += "ModelProbability fixed: $fixedModelCount"
$lines += "SEND_OK: $sendOkCount"
$lines += "REVIEW_ONLY: $reviewOnlyCount"
$lines += "BLOCKED: $blockedOfficialCount"
$lines += ""

$lines += "CLIENT-SAFE RANKER RESULT"
if ($sendOkCount -eq 0) {
    $lines += "- No client-safe official picks."
} else {
    foreach ($r in ($safeRows | Where-Object { $_.clientSafeDecision -eq "CLIENT_OFFICIAL_SEND_OK" })) {
        $lines += "- OFFICIAL | $($r.pick) | $($r.game) | Model $($r.modelProbabilityText)"
    }
}
$lines += ""

$lines += "BLOCKED / REVIEW SAMPLE"
foreach ($r in ($safeRows | Where-Object { $_.clientSafeDecision -ne "CLIENT_OFFICIAL_SEND_OK" } | Select-Object -First 20)) {
    $lines += "- $($r.clientSafeDecision) | $($r.pick) | $($r.game)"
    if ($r.hardBlocks -ne "") { $lines += "  Hard: $($r.hardBlocks)" }
    if ($r.warnings -ne "") { $lines += "  Warn: $($r.warnings)" }
}
$lines += ""

$lines += "IMPORTANT"
$lines += "This script writes a client-safe ranker COPY. It does not overwrite the original ranker."
$lines += "Next step is to patch 198_baseballpred_full_slate_ranker.py or make the daily runner consume this safe copy."

$safeRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
