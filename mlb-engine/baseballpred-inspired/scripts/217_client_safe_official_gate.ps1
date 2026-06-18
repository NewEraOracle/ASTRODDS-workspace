$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-client-safe-official-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-client-safe-official-gate-latest.json"
$outCsv  = Join-Path $astro "ASTRODDS-client-safe-official-gate-latest.csv"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 217 CLIENT SAFE OFFICIAL GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - PREVENT FAKE OFFICIAL PICKS" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return (Get-Content $path -Raw | ConvertFrom-Json) }
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

$lockedRows = @(Normalize-Rows (Read-JsonSafe $lockedOfficial))

$public = Read-JsonSafe $publicBoard
$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$ranker = Read-JsonSafe $rankerFile
$rankerRows = @()
if ($null -ne $ranker -and $ranker.gameBoard) {
    $rankerRows = @(Normalize-Rows $ranker.gameBoard)
}

$csvRows = @()
if (Test-Path $fullSlateCsv) {
    try { $csvRows = @(Import-Csv $fullSlateCsv) }
    catch { $csvRows = @() }
}

$safeRows = @()
$lines = @()

$lines += "ASTRODDS 217 CLIENT SAFE OFFICIAL GATE"
$lines += ""
$lines += "Goal: stop fake OFFICIAL picks when sources are not fully connected/calibrated."
$lines += ""
$lines += "Input locked picks: $($lockedRows.Count)"
$lines += ""

foreach ($o in $lockedRows) {
    $game = "$($o.Game)".Trim()
    $pick = "$($o.Pick)".Trim()

    if ($game -eq "" -or $pick -eq "") { continue }

    $hardBlocks = @()
    $warnings = @()
    $info = @()

    $lockedPrice = Num $o.Price
    $lockedModel = Num $o.ModelProbability
    $lockedEdgePct = Num $o.EdgePct

    if ($null -eq $lockedPrice -or $lockedPrice -le 0 -or $lockedPrice -ge 1) {
        $hardBlocks += "Invalid locked market price."
    }

    if ($null -eq $lockedModel -or $lockedModel -le 0 -or $lockedModel -ge 1) {
        $hardBlocks += "Invalid locked model probability."
    }

    if ($null -eq $lockedEdgePct -or $lockedEdgePct -le 0) {
        $hardBlocks += "Invalid locked edge."
    }

    $pub = $publicAPicks | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $pub) {
        $hardBlocks += "Missing from public board aPicks."
    } else {
        $marketConnected = Get-Prop $pub "marketConnected"
        $pubMarket = Num (Get-Prop $pub "market")
        $pubModel = Num (Get-Prop $pub "model")
        $pubEdge = Num (Get-Prop $pub "edge")

        if (!(Is-TrueText $marketConnected)) {
            $hardBlocks += "Public board marketConnected is not true."
        }

        if ($null -eq $pubMarket -or $pubMarket -le 0 -or $pubMarket -ge 1) {
            $hardBlocks += "Public board market is invalid."
        }

        if ($null -eq $pubModel -or $pubModel -le 0 -or $pubModel -ge 1) {
            $hardBlocks += "Public board model is invalid."
        }

        if ($null -eq $pubEdge -or $pubEdge -le 0) {
            $hardBlocks += "Public board edge is invalid."
        }
    }

    $rank = $rankerRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $rank) {
        $rank = $rankerRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $rankerModel = $null
    $rankerStatus = ""

    if ($null -eq $rank) {
        $hardBlocks += "Missing from ranker gameBoard."
    } else {
        $rankerStatus = FirstNonEmpty $rank @("status", "category")
        $rankerModelText = FirstNonEmpty $rank @("modelProbability", "ModelProbability")
        $rankerModel = Num $rankerModelText

        if ("$rankerStatus" -match "PAPER") {
            $hardBlocks += "Ranker status contains PAPER."
        }

        if ($null -eq $rankerModel) {
            $hardBlocks += "Ranker modelProbability is empty."
        }

        $info += "Ranker status: $rankerStatus"
    }

    $csv = $csvRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $csv) {
        $csv = $csvRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $fullSlateModel = $null
    $fullSlateMarket = $null
    $lineupStatus = ""

    if ($null -eq $csv) {
        $hardBlocks += "Missing from full slate context CSV."
    } else {
        $paperOnly = "$($csv.paperOnly)"
        $fullSlateModel = Num $csv.modelProbability
        $fullSlateMarket = Num $csv.marketProbability
        $awayLineup = "$($csv.awayLineupStatus)"
        $homeLineup = "$($csv.homeLineupStatus)"
        $lineupStatus = "away=$awayLineup home=$homeLineup"

        if (Is-TrueText $paperOnly) {
            $hardBlocks += "Full slate paperOnly=True."
        }

        if ($awayLineup -eq "missing" -or $homeLineup -eq "missing") {
            $warnings += "Lineups missing. Downgrade to REVIEW_ONLY until confirmed."
        }

        if ($null -eq $fullSlateModel) {
            $hardBlocks += "Full slate modelProbability is missing."
        }

        if ($null -eq $fullSlateMarket) {
            $warnings += "Full slate marketProbability is missing."
        }
    }

    if ($null -ne $lockedModel -and $null -ne $fullSlateModel) {
        $modelDiff = [math]::Abs($lockedModel - $fullSlateModel)

        if ($modelDiff -gt 0.05) {
            $hardBlocks += "Model mismatch above 5%: locked $(Pct $lockedModel) vs fullSlate $(Pct $fullSlateModel)."
        }
    }

    if ($null -ne $lockedPrice -and $null -ne $fullSlateMarket) {
        $marketDiff = [math]::Abs($lockedPrice - $fullSlateMarket)

        if ($marketDiff -gt 0.03) {
            $warnings += "Market mismatch above 3 cents: locked $(Cents $lockedPrice) vs fullSlate $(Cents $fullSlateMarket)."
        }
    }

    $decision = "CLIENT_OFFICIAL_SEND_OK"

    if ($hardBlocks.Count -gt 0) {
        $decision = "BLOCKED_FOR_REVIEW"
    } elseif ($warnings.Count -gt 0) {
        $decision = "REVIEW_ONLY"
    }

    $safeRows += ,[pscustomobject]@{
        Decision = $decision
        Pick = $pick
        Game = $game
        Price = Cents $lockedPrice
        LockedModel = Pct $lockedModel
        FullSlateModel = Pct $fullSlateModel
        Edge = Pct $lockedEdgePct
        RankerModelPresent = if ($null -ne $rankerModel) { "YES" } else { "NO" }
        Lineups = $lineupStatus
        HardBlocks = ($hardBlocks -join " | ")
        Warnings = ($warnings -join " | ")
        Info = ($info -join " | ")
    }
}

$sendOk = @($safeRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$review = @($safeRows | Where-Object { $_.Decision -eq "REVIEW_ONLY" }).Count
$blocked = @($safeRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count

$clientDecision = "CLIENT_DROP_ALLOWED"
if ($blocked -gt 0) {
    $clientDecision = "CLIENT_DROP_BLOCKED"
} elseif ($review -gt 0) {
    $clientDecision = "CLIENT_DROP_REVIEW_ONLY"
}

$lines += "SUMMARY"
$lines += "CLIENT DECISION: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW_ONLY: $review"
$lines += "BLOCKED: $blocked"
$lines += ""

$lines += "PICK GATE"
$lines += ""

foreach ($r in $safeRows) {
    $lines += "$($r.Decision) | $($r.Pick)"
    $lines += "Game: $($r.Game)"
    $lines += "Value: $($r.Price) | Locked model: $($r.LockedModel) | Full slate model: $($r.FullSlateModel) | Edge: $($r.Edge)"
    $lines += "Ranker model present: $($r.RankerModelPresent)"
    $lines += "Lineups: $($r.Lineups)"

    if ($r.HardBlocks -ne "") {
        $lines += "Hard blocks: $($r.HardBlocks)"
    }

    if ($r.Warnings -ne "") {
        $lines += "Warnings: $($r.Warnings)"
    }

    if ($r.Info -ne "") {
        $lines += "Info: $($r.Info)"
    }

    $lines += ""
}

$lines += "POLICY LOCKED"
$lines += "A pick can be CLIENT_OFFICIAL only if:"
$lines += "- public board aPick exists"
$lines += "- marketConnected=True"
$lines += "- market/model/edge are valid"
$lines += "- full slate paperOnly is not True"
$lines += "- ranker modelProbability is present"
$lines += "- public/locked model matches full slate model within 5%"
$lines += "- lineups are confirmed, otherwise REVIEW_ONLY"
$lines += ""
$lines += "Current action: do not send blocked picks to clients."

$safeRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$safeRows | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
