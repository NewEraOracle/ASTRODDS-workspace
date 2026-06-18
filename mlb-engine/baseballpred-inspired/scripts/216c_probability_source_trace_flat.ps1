$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$engineSignals  = Join-Path $astro "ASTRODDS-engine-final-signals-latest.json"

$outTxt  = Join-Path $astro "ASTRODDS-probability-source-trace-flat-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-probability-source-trace-flat-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-probability-source-trace-flat-latest.json"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 216C PROBABILITY SOURCE TRACE FLAT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - NO COMPLEX OBJECTS" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) {
        return $null
    }

    try {
        return (Get-Content $path -Raw | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }

    if ($data -is [System.Array]) {
        return @($data)
    }

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

                        if ($i -lt $arr.Count) {
                            $h[$p.Name] = $arr[$i]
                        } else {
                            $h[$p.Name] = ""
                        }
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
    if ($null -eq $n) { return "" }

    if ($n -le 1) {
        $n = $n * 100
    }

    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "" }

    if ($n -le 1) {
        $n = $n * 100
    }

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

function Make-TraceRow($pick, $game, $source, $row, $note) {
    if ($null -eq $row) {
        return [pscustomobject]@{
            Pick = $pick
            Game = $game
            Source = $source
            Found = "NO"
            Status = ""
            PaperOnly = ""
            TelegramEligible = ""
            Market = ""
            Model = ""
            CalibratedModel = ""
            Edge = ""
            Lineups = ""
            Decision = ""
            Note = $note
        }
    }

    $market = FirstNonEmpty $row @("market", "marketProbability", "price", "Price")
    $model = FirstNonEmpty $row @("model", "modelProbability", "ModelProbability", "rawModelProbability")
    $calib = FirstNonEmpty $row @("calibratedProbabilityV2", "calibratedPickProbabilityForThreshold", "calibratedProbability")
    $edge = FirstNonEmpty $row @("edge", "edgePct", "EdgePct", "calibratedEdgePct", "rawEdgePct")
    $status = FirstNonEmpty $row @("status", "category", "finalEngineDecision", "calibratedDecision", "strictFullSlateDecision", "fullContextDecision")
    $decision = FirstNonEmpty $row @("finalEngineDecision", "calibratedDecision", "strictFullSlateDecision", "fullContextDecision")
    $paper = FirstNonEmpty $row @("paperOnly", "PaperOnly")
    $telegram = FirstNonEmpty $row @("telegramEligible", "TelegramEligible")

    $awayLineup = FirstNonEmpty $row @("awayLineupStatus")
    $homeLineup = FirstNonEmpty $row @("homeLineupStatus")

    $lineups = ""
    if ($awayLineup -ne "" -or $homeLineup -ne "") {
        $lineups = "away=$awayLineup home=$homeLineup"
    }

    return [pscustomobject]@{
        Pick = $pick
        Game = $game
        Source = $source
        Found = "YES"
        Status = $status
        PaperOnly = $paper
        TelegramEligible = $telegram
        Market = Cents $market
        Model = Pct $model
        CalibratedModel = Pct $calib
        Edge = Pct $edge
        Lineups = $lineups
        Decision = $decision
        Note = $note
    }
}

$officialRows = @(Normalize-Rows (Read-JsonSafe $lockedOfficial))

$public = Read-JsonSafe $publicBoard
$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$ranker = Read-JsonSafe $rankerFile
$gameBoard = @()
if ($null -ne $ranker -and $ranker.gameBoard) {
    $gameBoard = @(Normalize-Rows $ranker.gameBoard)
}

$engine = Read-JsonSafe $engineSignals
$engineRows = @(Normalize-Rows $engine)

$csvRows = @()
if (Test-Path $fullSlateCsv) {
    try {
        $csvRows = @(Import-Csv $fullSlateCsv)
    } catch {
        $csvRows = @()
    }
}

$lines = @()
$traceRows = @()

$lines += "ASTRODDS 216C PROBABILITY SOURCE TRACE FLAT"
$lines += ""
$lines += "Purpose: find why public board says OFFICIAL while integrity gate blocks the client drop."
$lines += ""
$lines += "Official locked picks checked: $($officialRows.Count)"
$lines += ""

foreach ($o in $officialRows) {
    $game = "$($o.Game)".Trim()
    $pick = "$($o.Pick)".Trim()

    if ($game -eq "" -or $pick -eq "") {
        continue
    }

    $pub = $publicAPicks | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    $rank = $gameBoard | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $rank) {
        $rank = $gameBoard | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $csv = $csvRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $csv) {
        $csv = $csvRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $eng = $engineRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $eng) {
        $eng = $engineRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    $traceRows += ,(Make-TraceRow $pick $game "LOCKED_210" $o "Locked official source.")
    $traceRows += ,(Make-TraceRow $pick $game "PUBLIC_BOARD_aPicks" $pub "Original public board aPick source.")
    $traceRows += ,(Make-TraceRow $pick $game "RANKER_gameBoard" $rank "Ranker board row.")
    $traceRows += ,(Make-TraceRow $pick $game "FULL_SLATE_CONTEXT_CSV" $csv "Full slate context row.")
    $traceRows += ,(Make-TraceRow $pick $game "ENGINE_FINAL_SIGNALS" $eng "Engine final signal row.")

    $causes = @()

    if ($null -eq $pub) {
        $causes += "Missing from public board aPicks."
    }

    if ($null -eq $csv) {
        $causes += "No full slate CSV row found."
    } else {
        if ("$($csv.paperOnly)" -eq "True" -or "$($csv.paperOnly)" -eq "true") {
            $causes += "Full slate says paperOnly=True."
        }

        if ("$($csv.awayLineupStatus)" -eq "missing" -or "$($csv.homeLineupStatus)" -eq "missing") {
            $causes += "Lineups missing in full slate context."
        }

        $lockedModel = Num $o.ModelProbability
        $csvModel = Num $csv.modelProbability

        if ($null -ne $lockedModel -and $null -ne $csvModel) {
            $diff = [math]::Abs($lockedModel - $csvModel)

            if ($diff -gt 0.10) {
                $causes += "Large model mismatch: locked $(Pct $lockedModel) vs full slate $(Pct $csvModel)."
            } elseif ($diff -gt 0.05) {
                $causes += "Medium model mismatch: locked $(Pct $lockedModel) vs full slate $(Pct $csvModel)."
            }
        }
    }

    if ($null -eq $rank) {
        $causes += "No ranker row found."
    } else {
        $rankModel = FirstNonEmpty $rank @("modelProbability", "ModelProbability")
        if ($rankModel -eq "") {
            $causes += "Ranker modelProbability is empty."
        }

        if ("$($rank.status)" -match "PAPER") {
            $causes += "Ranker status contains PAPER."
        }
    }

    if ($causes.Count -eq 0) {
        $causes += "No obvious cause found. Manual review needed."
    }

    $lines += "============================================================"
    $lines += "PICK: $pick"
    $lines += "GAME: $game"
    $lines += "LOCKED: Price $(Cents $o.Price) | Model $(Pct $o.ModelProbability) | Edge $(Pct $o.EdgePct)"
    $lines += "ROOT CAUSES"

    foreach ($c in $causes) {
        $lines += "- $c"
    }

    $lines += ""
}

$lines += "============================================================"
$lines += "FINAL RECOMMENDATION"
$lines += "Keep CLIENT_DROP_BLOCKED until:"
$lines += "1. paperOnly is false or absent for official picks"
$lines += "2. ranker modelProbability is not empty"
$lines += "3. public board model and full slate model match within 5%"
$lines += "4. lineups are confirmed or picks are downgraded to REVIEW_ONLY"
$lines += ""
$lines += "Current state: do not send these as client official picks."

$traceRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$traceRows | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
