$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$publicBoard = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$rankerFile  = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$fullSlate   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$gateCsv     = Join-Path $astro "ASTRODDS-client-safe-official-gate-latest.csv"

$outJson = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.json"
$outCsv  = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.csv"
$outTxt  = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.txt"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 219 CLIENT SAFE PUBLIC BOARD" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - BLOCK FAKE OFFICIAL PICKS" -ForegroundColor Cyan
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

$public = Read-JsonSafe $publicBoard
$ranker = Read-JsonSafe $rankerFile

$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$rankerRows = @()
if ($null -ne $ranker -and $ranker.gameBoard) {
    $rankerRows = @(Normalize-Rows $ranker.gameBoard)
}

$fullSlateRows = @()
if (Test-Path $fullSlate) {
    try { $fullSlateRows = @(Import-Csv $fullSlate) }
    catch { $fullSlateRows = @() }
}

$gateRows = @()
if (Test-Path $gateCsv) {
    try { $gateRows = @(Import-Csv $gateCsv) }
    catch { $gateRows = @() }
}

$allRows = @()
$official = @()
$review = @()
$blocked = @()
$noBet = @()

foreach ($p in $publicAPicks) {
    $game = "$($p.game)".Trim()
    $pick = "$($p.pick)".Trim()

    if ($game -eq "" -or $pick -eq "") { continue }

    $hard = @()
    $warn = @()

    $market = Num (FirstNonEmpty $p @("market", "marketProbability", "price"))
    $model = Num (FirstNonEmpty $p @("model", "modelProbability", "ModelProbability"))
    $edge = Num (FirstNonEmpty $p @("edge", "edgePct", "EdgePct"))
    $marketConnected = FirstNonEmpty $p @("marketConnected")

    if (!(Is-TrueText $marketConnected)) {
        $hard += "marketConnected is not true"
    }

    if ($null -eq $market -or $market -le 0 -or $market -ge 1) {
        $hard += "invalid market price"
    }

    if ($null -eq $model -or $model -le 0 -or $model -ge 1) {
        $hard += "invalid model probability"
    }

    if ($null -eq $edge -or $edge -le 0) {
        $hard += "invalid or non-positive edge"
    }

    $rank = $rankerRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $rank) {
        $rank = $rankerRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $rankModel = $null
    if ($null -eq $rank) {
        $hard += "missing ranker row"
    } else {
        $rankModelText = FirstNonEmpty $rank @("modelProbability", "ModelProbability")
        $rankModel = Num $rankModelText

        if ($null -eq $rankModel) {
            $hard += "ranker modelProbability is empty"
        }

        $rankStatus = FirstNonEmpty $rank @("status", "category")
        if ($rankStatus -match "PAPER") {
            $hard += "ranker status contains PAPER"
        }
    }

    $slate = $fullSlateRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $slate) {
        $slate = $fullSlateRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $fullModel = $null

    if ($null -eq $slate) {
        $hard += "missing full slate row"
    } else {
        if (Is-TrueText "$($slate.paperOnly)") {
            $hard += "full slate paperOnly=True"
        }

        $fullModel = Num $slate.modelProbability

        if ($null -eq $fullModel) {
            $hard += "full slate modelProbability missing"
        }

        if ("$($slate.awayLineupStatus)" -eq "missing" -or "$($slate.homeLineupStatus)" -eq "missing") {
            $warn += "lineups missing"
        }
    }

    if ($null -ne $model -and $null -ne $fullModel) {
        $diff = [math]::Abs($model - $fullModel)

        if ($diff -gt 0.05) {
            $hard += "model mismatch above 5%: public $(Pct $model) vs fullSlate $(Pct $fullModel)"
        }
    }

    $decision = "CLIENT_OFFICIAL_SEND_OK"
    $category = "OFFICIAL"

    if ($hard.Count -gt 0) {
        $decision = "BLOCKED_FOR_REVIEW"
        $category = "BLOCKED"
    } elseif ($warn.Count -gt 0) {
        $decision = "REVIEW_ONLY"
        $category = "REVIEW_ONLY"
    }

    $row = [pscustomobject]@{
        Decision = $decision
        Category = $category
        MarketType = "MONEYLINE"
        Game = $game
        Pick = $pick
        Price = Cents $market
        ModelProbability = Pct $model
        FullSlateModel = Pct $fullModel
        Edge = Pct $edge
        TelegramEligible = if ($decision -eq "CLIENT_OFFICIAL_SEND_OK") { "true" } else { "false" }
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
        Source = "219_client_safe_public_board"
    }

    $allRows += ,$row

    if ($decision -eq "CLIENT_OFFICIAL_SEND_OK") {
        $official += ,$row
    } elseif ($decision -eq "REVIEW_ONLY") {
        $review += ,$row
    } else {
        $blocked += ,$row
    }
}

$sendOk = $official.Count
$reviewCount = $review.Count
$blockedCount = $blocked.Count

$clientDecision = "CLIENT_DROP_ALLOWED"
if ($blockedCount -gt 0) {
    $clientDecision = "CLIENT_DROP_BLOCKED"
} elseif ($reviewCount -gt 0) {
    $clientDecision = "CLIENT_DROP_REVIEW_ONLY"
}

$out = [ordered]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOk
    reviewOnly = $reviewCount
    blocked = $blockedCount
    officialPicks = @($official)
    reviewOnlyPicks = @($review)
    blockedPicks = @($blocked)
    allRows = @($allRows)
    rule = "Client safe board. OFFICIAL impossible when paperOnly=True, ranker modelProbability empty, full slate missing, model mismatch above 5%, or lineups missing."
}

$lines = @()
$lines += "ASTRODDS 219 CLIENT SAFE PUBLIC BOARD"
$lines += ""
$lines += "CLIENT DECISION: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW_ONLY: $reviewCount"
$lines += "BLOCKED: $blockedCount"
$lines += ""

$lines += "SAFE OFFICIAL PICKS"
if ($official.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $official) {
        $lines += "- $($r.Pick) | $($r.Game) | $($r.Price) | Model $($r.ModelProbability) | Edge $($r.Edge)"
    }
}
$lines += ""

$lines += "REVIEW ONLY"
if ($review.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $review) {
        $lines += "- $($r.Pick) | $($r.Game) | Warnings: $($r.Warnings)"
    }
}
$lines += ""

$lines += "BLOCKED"
if ($blocked.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $blocked) {
        $lines += "- $($r.Pick) | $($r.Game)"
        $lines += "  Hard blocks: $($r.HardBlocks)"
        if ($r.Warnings -ne "") {
            $lines += "  Warnings: $($r.Warnings)"
        }
    }
}
$lines += ""

$lines += "POLICY"
$lines += "No client Telegram official message should be built unless CLIENT DECISION is CLIENT_DROP_ALLOWED."

$allRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
