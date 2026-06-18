$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$gateCsv  = Join-Path $astro "ASTRODDS-client-safe-official-gate-latest.csv"
$traceCsv = Join-Path $astro "ASTRODDS-probability-source-trace-flat-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-official-generator-source-map-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-official-generator-source-map-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-official-generator-source-map-latest.json"

Write-Host ""
Write-Host "ASTRODDS 218 FIND OFFICIAL GENERATOR + BROKEN FIELDS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - SOURCE MAP" -ForegroundColor Cyan
Write-Host ""

$targets = @(
    "ASTRODDS-public-board-categories-latest.json",
    "ASTRODDS-baseballpred-full-slate-ranker-latest.json",
    "ASTRODDS-full-slate-context-final-latest.csv",
    "ASTRODDS-moneyline-official-source-locked-latest.json",
    "aPicks",
    "OFFICIAL",
    "telegramEligible",
    "paperOnly",
    "modelProbability",
    "marketConnected",
    "fullSlateModel",
    "baseballPredScore",
    "status"
)

$extensions = @(".ps1", ".psm1", ".js", ".ts", ".tsx", ".mjs", ".cjs", ".json")

$excludedParts = @(
    "\node_modules\",
    "\.next\",
    "\.git\",
    "\dist\",
    "\build\",
    "\coverage\"
)

function Is-Excluded($path) {
    foreach ($x in $excludedParts) {
        if ($path -like "*$x*") {
            return $true
        }
    }
    return $false
}

function Safe-Line($s) {
    if ($null -eq $s) { return "" }
    $x = "$s".Trim()
    if ($x.Length -gt 240) {
        return $x.Substring(0, 240)
    }
    return $x
}

$hits = @()

$files = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $extensions -contains $_.Extension.ToLower() -and !(Is-Excluded $_.FullName)
    }

foreach ($file in $files) {
    $content = @()

    try {
        $content = Get-Content $file.FullName -ErrorAction Stop
    } catch {
        continue
    }

    for ($i = 0; $i -lt $content.Count; $i++) {
        $line = "$($content[$i])"

        foreach ($target in $targets) {
            if ($line -like "*$target*") {
                $hits += ,[pscustomobject]@{
                    Target = $target
                    File = $file.FullName
                    LineNumber = $i + 1
                    LastWriteTime = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
                    Line = Safe-Line $line
                }
            }
        }
    }
}

$likelyPublicWriters = @($hits | Where-Object {
    $_.Target -eq "ASTRODDS-public-board-categories-latest.json"
} | Sort-Object File, LineNumber)

$likelyRankerWriters = @($hits | Where-Object {
    $_.Target -eq "ASTRODDS-baseballpred-full-slate-ranker-latest.json"
} | Sort-Object File, LineNumber)

$likelyFullSlateWriters = @($hits | Where-Object {
    $_.Target -eq "ASTRODDS-full-slate-context-final-latest.csv"
} | Sort-Object File, LineNumber)

$paperOnlyHits = @($hits | Where-Object {
    $_.Target -eq "paperOnly"
} | Sort-Object File, LineNumber)

$modelProbabilityHits = @($hits | Where-Object {
    $_.Target -eq "modelProbability"
} | Sort-Object File, LineNumber)

$officialHits = @($hits | Where-Object {
    $_.Target -eq "OFFICIAL"
} | Sort-Object File, LineNumber)

$gateRows = @()
if (Test-Path $gateCsv) {
    try { $gateRows = @(Import-Csv $gateCsv) } catch { $gateRows = @() }
}

$traceRows = @()
if (Test-Path $traceCsv) {
    try { $traceRows = @(Import-Csv $traceCsv) } catch { $traceRows = @() }
}

$lines = @()

$lines += "ASTRODDS 218 FIND OFFICIAL GENERATOR + BROKEN FIELDS"
$lines += ""
$lines += "CURRENT SAFETY STATUS"
$lines += ""

if ($gateRows.Count -gt 0) {
    $sendOk = @($gateRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
    $review = @($gateRows | Where-Object { $_.Decision -eq "REVIEW_ONLY" }).Count
    $blocked = @($gateRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count

    $lines += "Gate rows found: $($gateRows.Count)"
    $lines += "SEND_OK: $sendOk"
    $lines += "REVIEW_ONLY: $review"
    $lines += "BLOCKED: $blocked"
    $lines += ""

    foreach ($r in $gateRows) {
        $lines += "$($r.Decision) | $($r.Pick)"
        $lines += "Hard blocks: $($r.HardBlocks)"
        $lines += "Warnings: $($r.Warnings)"
        $lines += ""
    }
} else {
    $lines += "No gate CSV found. Run 217 first."
    $lines += ""
}

$lines += "SOURCE SEARCH SUMMARY"
$lines += "Files scanned: $($files.Count)"
$lines += "Total hits: $($hits.Count)"
$lines += ""

$lines += "LIKELY PUBLIC BOARD WRITERS"
if ($likelyPublicWriters.Count -eq 0) {
    $lines += "- No direct writer found for ASTRODDS-public-board-categories-latest.json"
} else {
    foreach ($h in ($likelyPublicWriters | Select-Object -First 20)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "LIKELY RANKER WRITERS"
if ($likelyRankerWriters.Count -eq 0) {
    $lines += "- No direct writer found for ASTRODDS-baseballpred-full-slate-ranker-latest.json"
} else {
    foreach ($h in ($likelyRankerWriters | Select-Object -First 20)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "LIKELY FULL SLATE WRITERS"
if ($likelyFullSlateWriters.Count -eq 0) {
    $lines += "- No direct writer found for ASTRODDS-full-slate-context-final-latest.csv"
} else {
    foreach ($h in ($likelyFullSlateWriters | Select-Object -First 20)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "PAPERONLY LOCATIONS"
foreach ($h in ($paperOnlyHits | Select-Object -First 40)) {
    $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
}
if ($paperOnlyHits.Count -eq 0) {
    $lines += "- No paperOnly hits found."
}
$lines += ""

$lines += "MODELPROBABILITY LOCATIONS"
foreach ($h in ($modelProbabilityHits | Select-Object -First 40)) {
    $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
}
if ($modelProbabilityHits.Count -eq 0) {
    $lines += "- No modelProbability hits found."
}
$lines += ""

$lines += "OFFICIAL LABEL LOCATIONS"
foreach ($h in ($officialHits | Select-Object -First 60)) {
    $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
}
if ($officialHits.Count -eq 0) {
    $lines += "- No OFFICIAL hits found."
}
$lines += ""

$lines += "TRACE CONFIRMATION"
if ($traceRows.Count -gt 0) {
    foreach ($t in $traceRows) {
        if ($t.Source -eq "FULL_SLATE_CONTEXT_CSV" -or $t.Source -eq "RANKER_gameBoard" -or $t.Source -eq "PUBLIC_BOARD_aPicks") {
            $lines += "$($t.Pick) | $($t.Source) | Found=$($t.Found) | Status=$($t.Status) | PaperOnly=$($t.PaperOnly) | Model=$($t.Model) | Lineups=$($t.Lineups)"
        }
    }
} else {
    $lines += "No trace CSV found. Run 216C first."
}
$lines += ""

$lines += "PATCH TARGET"
$lines += "Patch the script that creates the public board/ranker so OFFICIAL is impossible when:"
$lines += "- full slate paperOnly=True"
$lines += "- ranker modelProbability is empty"
$lines += "- public board model and full slate model differ by more than 5%"
$lines += "- lineups are missing, then downgrade to REVIEW_ONLY"
$lines += ""
$lines += "Current action: keep client drop blocked."

$hits | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$flatSummary = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    filesScanned = $files.Count
    totalHits = $hits.Count
    publicBoardWriterHits = $likelyPublicWriters.Count
    rankerWriterHits = $likelyRankerWriters.Count
    fullSlateWriterHits = $likelyFullSlateWriters.Count
    paperOnlyHits = $paperOnlyHits.Count
    modelProbabilityHits = $modelProbabilityHits.Count
    officialLabelHits = $officialHits.Count
    recommendation = "Patch official generator to respect client-safe gate."
}

$flatSummary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
