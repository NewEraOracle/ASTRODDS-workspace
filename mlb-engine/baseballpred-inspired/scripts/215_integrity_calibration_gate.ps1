$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$lockedOfficial = Join-Path $astro "ASTRODDS-moneyline-official-source-locked-latest.json"
$publicBoard    = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$rankerFile     = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
$fullSlateCsv   = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$engineSignals  = Join-Path $astro "ASTRODDS-engine-final-signals-latest.json"

$outTxt  = Join-Path $astro "ASTRODDS-integrity-calibration-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-integrity-calibration-gate-latest.json"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 215 INTEGRITY + CALIBRATION GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLIENT DROP SAFETY CHECK" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }

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
                        if ($i -lt $arr.Count) {
                            $h[$p.Name] = $arr[$i]
                        } else {
                            $h[$p.Name] = $null
                        }
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

function IsProb($v) {
    $n = Num $v
    if ($null -eq $n) { return $false }
    return ($n -gt 0 -and $n -lt 1)
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

function Has-True($obj, $name) {
    $v = Get-Prop $obj $name
    return ($v -eq "True" -or $v -eq "true" -or $v -eq "1")
}

function Find-CalibrationFiles {
    $patterns = @(
        "*training_report*.json",
        "*calibration*.json",
        "*backtest*.json",
        "*results-tracker*.json",
        "*settled*.json",
        "*outcomes*.json"
    )

    $found = @()

    foreach ($pat in $patterns) {
        try {
            $found += @(Get-ChildItem -Path $root -Recurse -File -Filter $pat -ErrorAction SilentlyContinue |
                Select-Object -First 10 |
                ForEach-Object { $_.FullName })
        } catch {}
    }

    return @($found | Sort-Object -Unique)
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
    try { $csvRows = @(Import-Csv $fullSlateCsv) } catch { $csvRows = @() }
}

$allGames = New-Object System.Collections.Generic.HashSet[string]

foreach ($r in $publicAPicks) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $gameBoard) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $csvRows) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}
foreach ($r in $engineRows) {
    if ($r.game) { [void]$allGames.Add("$($r.game)") }
}

$calibrationFiles = @(Find-CalibrationFiles)

$officialAuditRows = @()
$globalHardBlocks = New-Object System.Collections.Generic.List[string]
$globalWarnings = New-Object System.Collections.Generic.List[string]

if ($allGames.Count -lt 10) {
    $globalHardBlocks.Add("Slate coverage too low: only $($allGames.Count) unique games found.")
}

if ($officialRows.Count -eq 0) {
    $globalHardBlocks.Add("No locked official picks found.")
}

if ($calibrationFiles.Count -eq 0) {
    $globalWarnings.Add("No calibration/backtest/result tracker file found. Historical performance is not fully verified.")
}

foreach ($o in $officialRows) {
    $game = "$($o.Game)".Trim()
    $pick = "$($o.Pick)".Trim()

    $hard = New-Object System.Collections.Generic.List[string]
    $warn = New-Object System.Collections.Generic.List[string]
    $info = New-Object System.Collections.Generic.List[string]

    $price = Num $o.Price
    $model = Num $o.ModelProbability
    $edgePct = Num $o.EdgePct

    if ($game -eq "" -or $pick -eq "") {
        $hard.Add("Missing game or pick.")
    }

    if ($null -eq $price -or $price -le 0 -or $price -ge 1) {
        $hard.Add("Invalid locked market price.")
    }

    if ($null -eq $model -or $model -le 0 -or $model -ge 1) {
        $hard.Add("Invalid locked model probability.")
    }

    if ($null -eq $edgePct -or $edgePct -le 0) {
        $hard.Add("Invalid locked edge.")
    }

    $pub = $publicAPicks | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $pub) {
        $hard.Add("Pick not found in public aPicks source.")
    } else {
        if (!(Has-True $pub "marketConnected")) {
            $hard.Add("Public board marketConnected is not true.")
        }

        $pubMarket = Num $pub.market
        $pubModel  = Num $pub.model
        $pubEdge   = Num $pub.edge

        if ($null -eq $pubMarket -or $pubMarket -le 0 -or $pubMarket -ge 1) {
            $hard.Add("Public board market is invalid.")
        }

        if ($null -eq $pubModel -or $pubModel -le 0 -or $pubModel -ge 1) {
            $hard.Add("Public board model is invalid.")
        }

        if ($null -eq $pubEdge -or $pubEdge -le 0) {
            $hard.Add("Public board edge is invalid.")
        }

        if ($null -ne $pubModel -and $null -ne $model) {
            $diff = [math]::Abs($pubModel - $model)
            if ($diff -gt 0.001) {
                $hard.Add("Locked model does not match public board model.")
            }
        }
    }

    $board = $gameBoard | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $board) {
        $warn.Add("Pick not found in ranker gameBoard with same game + pick.")
    } else {
        $boardStatus = Get-Prop $board "status"
        $boardTelegram = Get-Prop $board "telegramEligible"
        $boardModel = Num (Get-Prop $board "modelProbability")

        $info.Add("Ranker status: $boardStatus")
        $info.Add("Ranker telegramEligible: $boardTelegram")

        if ($boardStatus -match "PAPER") {
            $hard.Add("Ranker marks this row as PAPER.")
        }

        if ($null -eq $boardModel) {
            $warn.Add("Ranker modelProbability is empty. Official model comes from public board only.")
        }
    }

    $csv = $csvRows | Where-Object {
        "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $csv) {
        $csv = $csvRows | Where-Object {
            "$($_.game)".Trim() -eq $game
        } | Select-Object -First 1
    }

    if ($null -eq $csv) {
        $warn.Add("No full slate CSV row matched this game.")
    } else {
        $csvModel = Num $csv.modelProbability
        $csvMarket = Num $csv.marketProbability
        $csvPaperOnly = "$($csv.paperOnly)"
        $awayLineup = "$($csv.awayLineupStatus)"
        $homeLineup = "$($csv.homeLineupStatus)"
        $awayPitcher = "$($csv.awayProbablePitcher)"
        $homePitcher = "$($csv.homeProbablePitcher)"

        if ($csvPaperOnly -eq "True" -or $csvPaperOnly -eq "true") {
            $hard.Add("Full slate row is paperOnly=True.")
        }

        if ($awayLineup -eq "missing" -or $homeLineup -eq "missing") {
            $warn.Add("Lineups are missing: away=$awayLineup, home=$homeLineup.")
        }

        if ($awayPitcher -eq "" -or $homePitcher -eq "") {
            $warn.Add("One probable pitcher is missing: away=[$awayPitcher], home=[$homePitcher].")
        }

        if ($null -ne $csvModel -and $null -ne $model) {
            $diff2 = [math]::Abs($csvModel - $model)

            if ($diff2 -gt 0.10) {
                $hard.Add("Large model mismatch vs full slate: locked $(Pct $model) vs fullSlate $(Pct $csvModel).")
            } elseif ($diff2 -gt 0.05) {
                $warn.Add("Medium model mismatch vs full slate: locked $(Pct $model) vs fullSlate $(Pct $csvModel).")
            }
        }

        if ($null -ne $csvMarket -and $null -ne $price) {
            $diff3 = [math]::Abs($csvMarket - $price)
            if ($diff3 -gt 0.03) {
                $warn.Add("Market mismatch vs full slate: locked $(Cents $price) vs fullSlate $(Cents $csvMarket).")
            }
        }
    }

    $decision = "SEND_OK"

    if ($hard.Count -gt 0) {
        $decision = "BLOCKED_FOR_REVIEW"
    } elseif ($warn.Count -gt 0) {
        $decision = "REVIEW_ONLY"
    }

    $officialAuditRows += [pscustomobject]@{
        Pick = $pick
        Game = $game
        Price = Cents $price
        Model = Pct $model
        Edge = Pct $edgePct
        Decision = $decision
        HardBlocks = @($hard)
        Warnings = @($warn)
        Info = @($info)
    }
}

$sendOkCount = @($officialAuditRows | Where-Object { $_.Decision -eq "SEND_OK" }).Count
$reviewCount = @($officialAuditRows | Where-Object { $_.Decision -eq "REVIEW_ONLY" }).Count
$blockedCount = @($officialAuditRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count

$clientDropDecision = "CLIENT_DROP_ALLOWED"

if ($globalHardBlocks.Count -gt 0 -or $blockedCount -gt 0) {
    $clientDropDecision = "CLIENT_DROP_BLOCKED"
} elseif ($reviewCount -gt 0 -or $globalWarnings.Count -gt 0) {
    $clientDropDecision = "CLIENT_DROP_REVIEW_ONLY"
}

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("ASTRODDS 215 INTEGRITY + CALIBRATION GATE")
$lines.Add("")
$lines.Add("GLOBAL CHECK")
$lines.Add("Unique games found: $($allGames.Count)")
$lines.Add("Locked official picks: $($officialRows.Count)")
$lines.Add("Calibration/backtest files found: $($calibrationFiles.Count)")
$lines.Add("SEND_OK picks: $sendOkCount")
$lines.Add("REVIEW_ONLY picks: $reviewCount")
$lines.Add("BLOCKED picks: $blockedCount")
$lines.Add("")
$lines.Add("CLIENT DROP DECISION: $clientDropDecision")
$lines.Add("")

if ($globalHardBlocks.Count -gt 0) {
    $lines.Add("GLOBAL HARD BLOCKS")
    foreach ($b in @($globalHardBlocks)) {
        $lines.Add("- $b")
    }
    $lines.Add("")
}

if ($globalWarnings.Count -gt 0) {
    $lines.Add("GLOBAL WARNINGS")
    foreach ($w in @($globalWarnings)) {
        $lines.Add("- $w")
    }
    $lines.Add("")
}

if ($calibrationFiles.Count -gt 0) {
    $lines.Add("CALIBRATION / BACKTEST FILES FOUND")
    foreach ($f in @($calibrationFiles | Select-Object -First 15)) {
        $lines.Add("- $f")
    }
    $lines.Add("")
}

$lines.Add("PICK AUDIT")
$lines.Add("")

foreach ($r in $officialAuditRows) {
    $lines.Add("$($r.Decision) | $($r.Pick)")
    $lines.Add("Game: $($r.Game)")
    $lines.Add("Value: $($r.Price) | Model: $($r.Model) | Edge: $($r.Edge)")

    if ($r.HardBlocks.Count -gt 0) {
        $lines.Add("Hard blocks:")
        foreach ($b in @($r.HardBlocks)) {
            $lines.Add("- $b")
        }
    }

    if ($r.Warnings.Count -gt 0) {
        $lines.Add("Warnings:")
        foreach ($w in @($r.Warnings)) {
            $lines.Add("- $w")
        }
    }

    if ($r.Info.Count -gt 0) {
        $lines.Add("Info:")
        foreach ($i in @($r.Info)) {
            $lines.Add("- $i")
        }
    }

    $lines.Add("")
}

$lines.Add("INTERPRETATION")
$lines.Add("- SEND_OK = connected, coherent, and no major warning.")
$lines.Add("- REVIEW_ONLY = data exists but not clean enough for client official drop.")
$lines.Add("- BLOCKED_FOR_REVIEW = do not send as official.")
$lines.Add("")
$lines.Add("IMPORTANT")
$lines.Add("This gate does not prove long-term profitability. For that, ASTRODDS needs settled result tracking, Brier/log loss, ROI, and win rate over many picks.")

$result = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDropDecision = $clientDropDecision
    uniqueGamesFound = $allGames.Count
    lockedOfficialCount = $officialRows.Count
    sendOkCount = $sendOkCount
    reviewOnlyCount = $reviewCount
    blockedCount = $blockedCount
    globalHardBlocks = @($globalHardBlocks)
    globalWarnings = @($globalWarnings)
    calibrationFilesFound = @($calibrationFiles)
    pickAudit = @($officialAuditRows)
}

$result | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
