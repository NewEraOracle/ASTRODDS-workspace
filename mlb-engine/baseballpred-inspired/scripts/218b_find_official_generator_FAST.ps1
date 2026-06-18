$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-official-generator-source-map-FAST-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-official-generator-source-map-FAST-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-official-generator-source-map-FAST-latest.json"

Write-Host ""
Write-Host "ASTRODDS 218B FAST OFFICIAL GENERATOR SOURCE MAP" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FAST TARGETED SEARCH" -ForegroundColor Cyan
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
    "baseballPredScore",
    "status"
)

$exts = @(".ps1", ".psm1", ".py", ".js", ".ts", ".tsx", ".mjs", ".cjs")

$searchRoots = @(
    (Join-Path $root "mlb-engine\baseballpred-inspired\scripts"),
    (Join-Path $root "mlb-engine\baseballpred-inspired"),
    (Join-Path $root "mlb-engine\scripts"),
    (Join-Path $root "scripts"),
    (Join-Path $root "app"),
    (Join-Path $root "src")
) | Where-Object { Test-Path $_ }

$excludedParts = @(
    "\node_modules\",
    "\.next\",
    "\.git\",
    "\dist\",
    "\build\",
    "\coverage\",
    "\.astrodds\"
)

function Is-Excluded($path) {
    foreach ($x in $excludedParts) {
        if ($path -like "*$x*") { return $true }
    }
    return $false
}

function Clean-Line($s) {
    if ($null -eq $s) { return "" }
    $x = "$s".Trim()
    if ($x.Length -gt 260) { return $x.Substring(0, 260) }
    return $x
}

$files = @()

foreach ($dir in $searchRoots) {
    Write-Host "Scanning root: $dir" -ForegroundColor DarkGray

    $found = Get-ChildItem -Path $dir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $exts -contains $_.Extension.ToLower() -and
            $_.Length -lt 3000000 -and
            !(Is-Excluded $_.FullName)
        }

    $files += @($found)
}

$files = @($files | Sort-Object FullName -Unique)

Write-Host "Candidate files: $($files.Count)" -ForegroundColor Green

$hits = @()
$sw = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($file in $files) {
    try {
        $matches = Select-String -LiteralPath $file.FullName -Pattern $targets -SimpleMatch -ErrorAction SilentlyContinue

        foreach ($m in @($matches)) {
            $hits += ,[pscustomobject]@{
                Target = "$($m.Pattern)"
                File = "$($m.Path)"
                LineNumber = $m.LineNumber
                LastWriteTime = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
                Line = Clean-Line $m.Line
            }
        }
    } catch {
        continue
    }
}

$sw.Stop()

$publicWriters = @($hits | Where-Object { $_.Target -eq "ASTRODDS-public-board-categories-latest.json" })
$rankerWriters = @($hits | Where-Object { $_.Target -eq "ASTRODDS-baseballpred-full-slate-ranker-latest.json" })
$fullSlateWriters = @($hits | Where-Object { $_.Target -eq "ASTRODDS-full-slate-context-final-latest.csv" })
$officialHits = @($hits | Where-Object { $_.Target -eq "OFFICIAL" })
$paperHits = @($hits | Where-Object { $_.Target -eq "paperOnly" })
$modelHits = @($hits | Where-Object { $_.Target -eq "modelProbability" })
$telegramHits = @($hits | Where-Object { $_.Target -eq "telegramEligible" })

$lines = @()

$lines += "ASTRODDS 218B FAST OFFICIAL GENERATOR SOURCE MAP"
$lines += ""
$lines += "Elapsed seconds: $([math]::Round($sw.Elapsed.TotalSeconds, 2))"
$lines += "Search roots: $($searchRoots.Count)"
$lines += "Candidate files scanned: $($files.Count)"
$lines += "Total hits: $($hits.Count)"
$lines += ""

$lines += "LIKELY PUBLIC BOARD WRITERS"
if ($publicWriters.Count -eq 0) {
    $lines += "- No direct writer found."
} else {
    foreach ($h in ($publicWriters | Select-Object -First 25)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "LIKELY RANKER WRITERS"
if ($rankerWriters.Count -eq 0) {
    $lines += "- No direct writer found."
} else {
    foreach ($h in ($rankerWriters | Select-Object -First 25)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "LIKELY FULL SLATE WRITERS"
if ($fullSlateWriters.Count -eq 0) {
    $lines += "- No direct writer found."
} else {
    foreach ($h in ($fullSlateWriters | Select-Object -First 25)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "OFFICIAL LABEL LOCATIONS"
if ($officialHits.Count -eq 0) {
    $lines += "- No OFFICIAL hits found."
} else {
    foreach ($h in ($officialHits | Select-Object -First 60)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "PAPERONLY LOCATIONS"
if ($paperHits.Count -eq 0) {
    $lines += "- No paperOnly hits found."
} else {
    foreach ($h in ($paperHits | Select-Object -First 40)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "MODELPROBABILITY LOCATIONS"
if ($modelHits.Count -eq 0) {
    $lines += "- No modelProbability hits found."
} else {
    foreach ($h in ($modelHits | Select-Object -First 40)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "TELEGRAMELIGIBLE LOCATIONS"
if ($telegramHits.Count -eq 0) {
    $lines += "- No telegramEligible hits found."
} else {
    foreach ($h in ($telegramHits | Select-Object -First 40)) {
        $lines += "- $($h.File):$($h.LineNumber) :: $($h.Line)"
    }
}
$lines += ""

$lines += "NEXT PATCH TARGET"
$lines += "Patch the file that writes public board/ranker OFFICIAL labels."
$lines += "OFFICIAL must be blocked when:"
$lines += "- paperOnly=True"
$lines += "- ranker modelProbability is empty"
$lines += "- full slate model missing"
$lines += "- model mismatch above 5%"
$lines += "- lineups missing, then REVIEW_ONLY"
$lines += ""
$lines += "Current client policy remains: CLIENT_DROP_BLOCKED."

$hits | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    elapsedSeconds = [math]::Round($sw.Elapsed.TotalSeconds, 2)
    candidateFilesScanned = $files.Count
    totalHits = $hits.Count
    publicBoardWriterHits = $publicWriters.Count
    rankerWriterHits = $rankerWriters.Count
    fullSlateWriterHits = $fullSlateWriters.Count
    officialHits = $officialHits.Count
    paperOnlyHits = $paperHits.Count
    modelProbabilityHits = $modelHits.Count
    telegramEligibleHits = $telegramHits.Count
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
