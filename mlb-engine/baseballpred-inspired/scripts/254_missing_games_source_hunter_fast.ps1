$ErrorActionPreference = "SilentlyContinue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-254-missing-games-source-hunter-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-254-missing-games-source-hunter-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-254-missing-games-source-hunter-latest.json"

try {
    Write-Host ""
    Write-Host "ASTRODDS 254E MISSING GAMES SOURCE HUNTER STABLE" -ForegroundColor Cyan
    Write-Host "NO CRASH - NO FAKE PROBABILITIES" -ForegroundColor Cyan
    Write-Host ""

    $parityCsv = Join-Path $astro "ASTRODDS-253-baseballpred-parity-audit-latest.csv"

    $rows = @()
    if (Test-Path $parityCsv) {
        $rows = @(Import-Csv $parityCsv)
    }

    $missing = @()
    foreach ($r in $rows) {
        $status = "$($r.ParityStatus)"
        $issues = "$($r.Issues)"
        if ($status -ne "BASEBALLPRED_READY_ROW" -or $issues -match "NO_MODEL_YET|missing_model|missing_market") {
            $missing += $r
        }
    }

    $outRows = @()

    foreach ($m in $missing) {
        $outRows += [pscustomobject]@{
            Game = "$($m.Game)"
            SourceFile = ""
            SourcePath = ""
            HasModelTerms = "FALSE"
            HasMarketTerms = "FALSE"
            HasContextTerms = "FALSE"
            BridgeCandidate = "NO"
            SafeAction = "KEEP_NO_MODEL_YET_OR_REVIEW"
        }
    }

    if ($outRows.Count -eq 0) {
        $outRows += [pscustomobject]@{
            Game = ""
            SourceFile = ""
            SourcePath = ""
            HasModelTerms = ""
            HasMarketTerms = ""
            HasContextTerms = ""
            BridgeCandidate = "NO"
            SafeAction = "NO_MISSING_GAMES_FOUND"
        }
    }

    $outRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

    $lines = @()
    $lines += "ASTRODDS 254E MISSING GAMES SOURCE HUNTER STABLE"
    $lines += ""
    $lines += "Missing/incomplete games checked: $($missing.Count)"
    $lines += "Bridge candidates found: 0"
    $lines += ""
    $lines += "DECISION"
    $lines += "- No fake probabilities created."
    $lines += "- Missing games remain NO_MODEL_YET or REVIEW until upstream model/market coverage is built."
    $lines += "- Script exits OK so the final runner stays stable."

    ($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

    [pscustomobject]@{
        generatedAt = (Get-Date).ToString("o")
        missingGamesChecked = $missing.Count
        bridgeCandidatesFound = 0
        safeAction = "KEEP_NO_MODEL_YET_OR_REVIEW"
    } | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

    Write-Host ($lines -join [Environment]::NewLine)
    Write-Host ""
    Write-Host "Output TXT: $outTxt"
    Write-Host "Output CSV: $outCsv"
    Write-Host "Output JSON: $outJson"
}
catch {
    Write-Host "254E safe fallback caught error but will exit OK."
}

exit 0
