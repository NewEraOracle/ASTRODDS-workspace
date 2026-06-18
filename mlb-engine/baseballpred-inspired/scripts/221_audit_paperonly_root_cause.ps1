$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$publicBoard = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$clientSafeRanker = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.csv"
$sourceScript = Join-Path $root "mlb-engine\baseballpred-inspired\scripts\37_full_slate_context_final_gate.py"

$outTxt = Join-Path $astro "ASTRODDS-paperonly-root-cause-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-paperonly-root-cause-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-paperonly-root-cause-audit-latest.json"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 221 PAPERONLY ROOT CAUSE AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY" -ForegroundColor Cyan
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

function Is-TrueText($v) {
    $s = "$v".Trim().ToLower()
    return ($s -eq "true" -or $s -eq "1" -or $s -eq "yes")
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

if (!(Test-Path $fullSlate)) {
    Write-Host "ERROR: full slate file missing:" -ForegroundColor Red
    Write-Host $fullSlate
    exit 0
}

$rows = @(Import-Csv $fullSlate)

$public = Read-JsonSafe $publicBoard
$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$safeRankerRows = @()
if (Test-Path $clientSafeRanker) {
    try { $safeRankerRows = @(Import-Csv $clientSafeRanker) }
    catch { $safeRankerRows = @() }
}

$paperTrue = @($rows | Where-Object { Is-TrueText "$($_.paperOnly)" })
$paperFalse = @($rows | Where-Object { !(Is-TrueText "$($_.paperOnly)") })

$lineupMissing = @($rows | Where-Object {
    "$($_.awayLineupStatus)" -eq "missing" -or "$($_.homeLineupStatus)" -eq "missing"
})

$modelPresent = @($rows | Where-Object {
    $n = Num $_.modelProbability
    $null -ne $n -and $n -gt 0 -and $n -lt 1
})

$marketPresent = @($rows | Where-Object {
    $n = Num $_.marketProbability
    $null -ne $n -and $n -gt 0 -and $n -lt 1
})

$officialPublicGames = New-Object System.Collections.Generic.HashSet[string]
foreach ($p in $publicAPicks) {
    if ($p.game) { [void]$officialPublicGames.Add("$($p.game)") }
}

$auditRows = @()

foreach ($r in $rows) {
    $game = "$($r.game)".Trim()
    $pick = "$($r.pick)".Trim()

    $safe = $safeRankerRows | Where-Object {
        "$($_.Game)".Trim() -eq $game -and "$($_.Pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -eq $safe) {
        $safe = $safeRankerRows | Where-Object {
            "$($_.game)".Trim() -eq $game -and "$($_.pick)".Trim() -eq $pick
        } | Select-Object -First 1
    }

    $reasons = @()

    if (Is-TrueText "$($r.paperOnly)") {
        $reasons += "paperOnly=True in full slate"
    }

    if ("$($r.awayLineupStatus)" -eq "missing" -or "$($r.homeLineupStatus)" -eq "missing") {
        $reasons += "lineups missing"
    }

    $mp = Num $r.modelProbability
    if ($null -eq $mp) {
        $reasons += "full slate modelProbability missing"
    }

    $mk = Num $r.marketProbability
    if ($null -eq $mk) {
        $reasons += "full slate marketProbability missing"
    }

    if ($officialPublicGames.Contains($game)) {
        $reasons += "game appears in public aPicks"
    }

    if ($null -ne $safe) {
        $decision = "$($safe.clientSafeDecision)"
        if ($decision -eq "") { $decision = "$($safe.Decision)" }
        if ($decision -ne "") {
            $reasons += "client-safe ranker decision=$decision"
        }
    }

    $auditRows += ,[pscustomobject]@{
        Game = $game
        Pick = $pick
        PaperOnly = "$($r.paperOnly)"
        ModelProbability = Pct $r.modelProbability
        MarketProbability = Pct $r.marketProbability
        AwayLineup = "$($r.awayLineupStatus)"
        HomeLineup = "$($r.homeLineupStatus)"
        StrictFullSlateDecision = "$($r.strictFullSlateDecision)"
        FullContextDecision = "$($r.fullContextDecision)"
        VvsEligible = "$($r.vvsEligible)"
        VvsReason = "$($r.vvsReason)"
        EdgePct = "$($r.edgePct)"
        Risk = "$($r.risk)"
        Reasons = ($reasons -join " | ")
    }
}

$scriptHits = @()
if (Test-Path $sourceScript) {
    $patterns = @("paperOnly", "True", "False", "manual", "review", "daily_pick", "status", "lineup")
    $matches = Select-String -LiteralPath $sourceScript -Pattern $patterns -SimpleMatch -ErrorAction SilentlyContinue

    foreach ($m in @($matches)) {
        $line = "$($m.Line)".Trim()
        if ($line.Length -gt 240) { $line = $line.Substring(0,240) }
        $scriptHits += ,[pscustomobject]@{
            File = $m.Path
            LineNumber = $m.LineNumber
            Pattern = $m.Pattern
            Line = $line
        }
    }
}

$lines = @()
$lines += "ASTRODDS 221 PAPERONLY ROOT CAUSE AUDIT"
$lines += ""
$lines += "FULL SLATE SUMMARY"
$lines += "Rows: $($rows.Count)"
$lines += "paperOnly=True: $($paperTrue.Count)"
$lines += "paperOnly=False/blank: $($paperFalse.Count)"
$lines += "Model probability present: $($modelPresent.Count)"
$lines += "Market probability present: $($marketPresent.Count)"
$lines += "Lineups missing rows: $($lineupMissing.Count)"
$lines += "Public aPick games: $($officialPublicGames.Count)"
$lines += ""

if ($paperTrue.Count -eq $rows.Count) {
    $lines += "MAJOR FINDING: Every full slate row has paperOnly=True."
    $lines += "This looks like a global safety flag or the full slate generator is intentionally marking all rows as paper-only."
} elseif ($paperTrue.Count -gt 0) {
    $lines += "Finding: Some rows are paperOnly=True, some are not."
} else {
    $lines += "Finding: No full slate rows are paperOnly=True."
}
$lines += ""

if ($lineupMissing.Count -eq $rows.Count) {
    $lines += "MAJOR FINDING: Every row has missing lineups."
    $lines += "This may be because lineups were not confirmed yet at scan time, or lineup source is not connected."
} elseif ($lineupMissing.Count -gt 0) {
    $lines += "Finding: Some rows have missing lineups."
}
$lines += ""

$lines += "PUBLIC A-PICK GAMES INSIDE FULL SLATE"
foreach ($g in @($officialPublicGames)) {
    $matches = @($auditRows | Where-Object { $_.Game -eq $g })
    if ($matches.Count -eq 0) {
        $lines += "- $g :: not found in full slate rows"
    } else {
        foreach ($m in $matches | Select-Object -First 3) {
            $lines += "- $($m.Game) | Pick=$($m.Pick) | PaperOnly=$($m.PaperOnly) | Model=$($m.ModelProbability) | Lineups=$($m.AwayLineup)/$($m.HomeLineup) | Reasons=$($m.Reasons)"
        }
    }
}
$lines += ""

$lines += "SOURCE SCRIPT paperOnly / status HITS"
if ($scriptHits.Count -eq 0) {
    $lines += "- No source script hits found or source script missing."
} else {
    foreach ($h in ($scriptHits | Select-Object -First 80)) {
        $lines += "- line $($h.LineNumber) [$($h.Pattern)] :: $($h.Line)"
    }
}
$lines += ""

$lines += "NEXT PATCH RECOMMENDATION"
$lines += "If paperOnly=True is global in 37_full_slate_context_final_gate.py, do not simply flip it to False."
$lines += "Instead, create a real rule:"
$lines += "- paperOnly=False only when modelProbability, marketProbability, game/pick match, no hard block, and context is connected."
$lines += "- if lineups missing, output REVIEW_ONLY."
$lines += "- if paperOnly=True, OFFICIAL must remain impossible."
$lines += ""
$lines += "Current client action: no official Telegram drop."

$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $rows.Count
    paperOnlyTrue = $paperTrue.Count
    paperOnlyFalseOrBlank = $paperFalse.Count
    modelProbabilityPresent = $modelPresent.Count
    marketProbabilityPresent = $marketPresent.Count
    lineupMissingRows = $lineupMissing.Count
    publicAPickGames = $officialPublicGames.Count
    sourceScriptHits = $scriptHits.Count
    majorFinding = if ($paperTrue.Count -eq $rows.Count) { "All full slate rows are paperOnly=True" } else { "Mixed paperOnly state" }
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
