$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$engineSignals  = Join-Path $astro "ASTRODDS-engine-final-signals-latest.json"
$gateFile       = Join-Path $astro "ASTRODDS-integrity-calibration-gate-latest.json"

$outTxt  = Join-Path $astro "ASTRODDS-probability-source-trace-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-probability-source-trace-latest.json"
$outCsv  = Join-Path $astro "ASTRODDS-probability-source-trace-latest.csv"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 216 PROBABILITY SOURCE TRACE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FIND WHY PICKS ARE BLOCKED" -ForegroundColor Cyan
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
        $_.Value -is [System.Array] -or ($_.Value -is [System.Collections.IEnumerable] -and !($_.Value -is [string]))
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
                    if (($v -is [System.Array]) -or ($v -is [System.Collections.IEnumerable] -and !($v -is [string]))) {
                        $arr = @($v)
                        if ($i -lt $arr.Count) { $h[$p.Name] = $arr[$i] }
                        else { $h[$p.Name] = $null }
                    } else {
                        $h[$p.Name] = $v
                    }
                }
                $rows += [pscustomobject]$h
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
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "" }
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

function Add-TraceRow($list, $source, $game, $pick, $row, $notes) {
    if ($null -eq $row) {
        $list.Add([pscustomobject]@{
            Source = $source
            Game = $game
            Pick = $pick
            Found = "NO"
            Status = ""
            PaperOnly = ""
            TelegramEligible = ""
            Market = ""
            Model = ""
            CalibratedModel = ""
            Edge = ""
            Decision = ""
            Lineups = ""
            Notes = $notes
        })
        return
    }

    $market = FirstNonEmpty $row @("market", "marketProbability", "price", "Price")
    $model = FirstNonEmpty $row @("model", "modelProbability", "ModelProbability", "rawModelProbability")
    $calib = FirstNonEmpty $row @("calibratedProbabilityV2", "calibratedPickProbabilityForThreshold", "calibratedProbability", "lockedEngineBuyProbabilityMin")
    $edge = FirstNonEmpty $row @("edge", "edgePct", "calibratedEdgePct", "rawEdgePct", "EdgePct")
    $status = FirstNonEmpty $row @("status", "category", "finalEngineDecision", "calibratedDecision", "strictFullSlateDecision", "fullContextDecision")
    $decision = FirstNonEmpty $row @("finalEngineDecision", "calibratedDecision", "strictFullSlateDecision", "fullContextDecision", "Decision")
    $paper = FirstNonEmpty $row @("paperOnly", "PaperOnly")
    $telegram = FirstNonEmpty $row @("telegramEligible", "TelegramEligible")
    $awayLineup = FirstNonEmpty $row @("awayLineupStatus")
    $homeLineup = FirstNonEmpty $row @("homeLineupStatus")
    $lineups = ""
    if ($awayLineup -ne "" -or $homeLineup -ne "") {
        $lineups = "away=$awayLineup home=$homeLineup"
    }

    $list.Add([pscustomobject]@{
        Source = $source
        Game = $game
        Pick = $pick
        Found = "YES"
        Status = $status
        PaperOnly = $paper
        TelegramEligible = $telegram
        Market = Cents $market
        Model = Pct $model
        CalibratedModel = Pct $calib
        Edge = Pct $edge
        Decision = $decision
        Lineups = $lineups
        Notes = $notes
    })
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

$gate = Read-JsonSafe $gateFile

$csvRows = @()
if (Test-Path $fullSlateCsv) {
    try { $csvRows = @(Import-Csv $fullSlateCsv) } catch { $csvRows = @() }
}

$traceRows = New-Object System.Collections.Generic.List[object]
$rootCauses = New-Object System.Collections.Generic.List[object]
$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("ASTRODDS 216 PROBABILITY SOURCE TRACE")
$lines.Add("")
$lines.Add("PURPOSE")
$lines.Add("Find why public board picks are marked OFFICIAL while integrity gate blocks them.")
$lines.Add("")

foreach ($o in $officialRows) {
    $game = "$($o.Game)".Trim()
    $pick = "$($o.Pick)".Trim()

    $lines.Add("============================================================")
    $lines.Add("PICK: $pick")
    $lines.Add("GAME: $game")
    $lines.Add("LOCKED: Price $(Cents $o.Price) | Model $(Pct $o.ModelProbability) | Edge $(Pct $o.EdgePct)")
    $lines.Add("")

    $pub = $publicAPicks | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    $rank = $gameBoard | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $rank) {
        $rank = $gameBoard | Where-Object { "$($_.game)".Trim() -eq $game } | Select-Object -First 1
    }

    $csv = $csvRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $csv) {
        $csv = $csvRows | Where-Object { "$($_.game)".Trim() -eq $game } | Select-Object -First 1
    }

    $eng = $engineRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $eng) {
        $eng = $engineRows | Where-Object { "$($_.game)".Trim() -eq $game } | Select-Object -First 1
    }

    Add-TraceRow $traceRows "LOCKED_210" $game $pick $o "Source currently used for locked official picks."
    Add-TraceRow $traceRows "PUBLIC_BOARD_aPicks" $game $pick $pub "Original public board official source."
    Add-TraceRow $traceRows "RANKER_gameBoard" $game $pick $rank "Ranker display board."
    Add-TraceRow $traceRows "FULL_SLATE_CONTEXT_CSV" $game $pick $csv "Full slate context row."
    Add-TraceRow $traceRows "ENGINE_FINAL_SIGNALS" $game $pick $eng "Engine final signal row if present."

    $causes = New-Object System.Collections.Generic.List[string]

    if ($null -eq $pub) {
        $causes.Add("Missing from public board aPicks.")
    }

    if ($null -ne $csv) {
        $paper = "$($csv.paperOnly)"
        if ($paper -eq "True" -or $paper -eq "true") {
            $causes.Add("Full slate says paperOnly=True. This alone blocks client official drop.")
        }

        $csvModel = Num $csv.modelProbability
        $lockedModel = Num $o.ModelProbability

        if ($null -ne $csvModel -and $null -ne $lockedModel) {
            $diff = [math]::Abs($csvModel - $lockedModel)
            if ($diff -gt 0.10) {
                $causes.Add("Large model mismatch: locked $(Pct $lockedModel) vs full slate $(Pct $csvModel).")
            } elseif ($diff -gt 0.05) {
                $causes.Add("Medium model mismatch: locked $(Pct $lockedModel) vs full slate $(Pct $csvModel).")
            }
        }

        if ("$($csv.awayLineupStatus)" -eq "missing" -or "$($csv.homeLineupStatus)" -eq "missing") {
            $causes.Add("Lineups missing in full slate context.")
        }
    } else {
        $causes.Add("No full slate CSV row found for this game.")
    }

    if ($null -ne $rank) {
        $rankModel = FirstNonEmpty $rank @("modelProbability", "ModelProbability")
        if ($rankModel -eq "") {
            $causes.Add("Ranker modelProbability is empty, so OFFICIAL label is not supported by ranker model field.")
        }

        if ("$($rank.status)" -match "PAPER") {
            $causes.Add("Ranker status contains PAPER.")
        }
    } else {
        $causes.Add("No ranker row found for this pick.")
    }

    if ($causes.Count -eq 0) {
        $causes.Add("No obvious cause found. Needs manual review.")
    }

    $rootCauses.Add([pscustomobject]@{
        Pick = $pick
        Game = $game
        Causes = @($causes)
    })

    $lines.Add("ROOT CAUSES")
    foreach ($c in @($causes)) {
        $lines.Add("- $c")
    }
    $lines.Add("")
}

$lines.Add("============================================================")
$lines.Add("FINAL POLICY RECOMMENDATION")
$lines.Add("")
$lines.Add("Set CLIENT OFFICIAL BUY to require ALL of these:")
$lines.Add("1. public board aPick exists")
$lines.Add("2. marketConnected=True")
$lines.Add("3. market price valid")
$lines.Add("4. model probability valid")
$lines.Add("5. full slate paperOnly is NOT True")
$lines.Add("6. ranker modelProbability is not empty OR full slate calibrated probability agrees within 5%")
$lines.Add("7. no model mismatch above 5%")
$lines.Add("8. lineups confirmed OR downgrade to REVIEW_ONLY")
$lines.Add("")
$lines.Add("Current state: KEEP CLIENT DROP BLOCKED until policy passes.")
$lines.Add("")

$traceRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$result = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialPicksChecked = $officialRows.Count
    clientDropStatus = "REMAIN_BLOCKED"
    rootCauses = @($rootCauses)
    traceRows = @($traceRows)
    recommendation = "Do not send these picks as official until paperOnly/model mismatch/ranker model issues are fixed."
}

$result | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Output CSV: $outCsv"
Write-Host ""
