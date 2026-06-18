$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
if (!(Test-Path $astro)) { New-Item -ItemType Directory -Force -Path $astro | Out-Null }

$outTxt = Join-Path $astro "ASTRODDS-385-real-data-fetch-error-diagnostic-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-385-real-data-fetch-error-diagnostic-latest.json"

Write-Host ""
Write-Host "ASTRODDS 385 REAL DATA FETCH ERROR DIAGNOSTIC" -ForegroundColor Cyan
Write-Host ""

$files = @(
    [pscustomobject]@{Name="xFIP 379"; Txt=(Join-Path $astro "ASTRODDS-379-fetch-true-xfip-fangraphs-pybaseball-latest.txt"); Csv=(Join-Path $astro "ASTRODDS-premium-input-starter-xfip.csv")},
    [pscustomobject]@{Name="Platoon 380"; Txt=(Join-Path $astro "ASTRODDS-380-fetch-team-platoon-statcast-pybaseball-latest.txt"); Csv=(Join-Path $astro "ASTRODDS-premium-input-team-platoon-splits.csv")},
    [pscustomobject]@{Name="Leverage 381"; Txt=(Join-Path $astro "ASTRODDS-381-fetch-true-leverage-fangraphs-pybaseball-latest.txt"); Csv=(Join-Path $astro "ASTRODDS-premium-input-bullpen-leverage-availability.csv")}
)

$items = @()
$lines = @()
$lines += "ASTRODDS 385 REAL DATA FETCH ERROR DIAGNOSTIC"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""

foreach ($f in $files) {
    $txtExists = Test-Path $f.Txt
    $csvExists = Test-Path $f.Csv
    $csvRows = 0
    $statusLine = ""
    $detailLines = @()

    if ($csvExists) {
        try { $csvRows = @(Import-Csv $f.Csv).Count } catch { $csvRows = 0 }
    }

    if ($txtExists) {
        $content = Get-Content $f.Txt
        $statusLine = ($content | Where-Object { $_ -match "^Status:" } | Select-Object -First 1)
        $detailStart = [array]::IndexOf($content, "DETAIL")
        if ($detailStart -ge 0) {
            $detailLines = @($content | Select-Object -Skip ($detailStart + 1) -First 30)
        } else {
            $detailLines = @($content | Select-Object -Last 30)
        }
    }

    $items += ,[pscustomobject]@{
        Name=$f.Name
        TxtExists=$txtExists
        CsvExists=$csvExists
        CsvRows=$csvRows
        StatusLine=$statusLine
        Detail=($detailLines -join "`n")
    }

    $lines += "===== $($f.Name) ====="
    $lines += "TXT exists: $txtExists"
    $lines += "CSV exists: $csvExists"
    $lines += "CSV rows: $csvRows"
    $lines += "$statusLine"
    $lines += ""
    $lines += "DETAIL / LAST ERROR"
    if ($detailLines.Count -gt 0) {
        foreach ($d in $detailLines) { $lines += $d }
    } else {
        $lines += "No detail available."
    }
    $lines += ""
}

$lines += "INTERPRETATION"
$lines += "- If xFIP says missing columns, pybaseball/FanGraphs output changed; we need map the displayed available columns."
$lines += "- If platoon says Statcast timeout/connection, rerun with -PlatoonDaysBack 7."
$lines += "- If leverage says missing gmLI/inLI/exLI, public fetch does not expose true leverage; keep CSV/manual source."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    items=@($items)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
