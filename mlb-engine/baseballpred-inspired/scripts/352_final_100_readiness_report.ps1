$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Get-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
}

function JVal($obj, $names, $default = "UNKNOWN") {
    if ($null -eq $obj) { return $default }
    foreach ($n in @($names)) {
        try {
            $p = $obj.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return $default
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-352-final-100-readiness-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-352-final-100-readiness-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 352B FINAL 100% READINESS REPORT - DISPLAY FIX" -ForegroundColor Cyan
Write-Host ""

$admin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$datasetJson = Join-Path $astro "ASTRODDS-350-training-dataset-from-settled-ledger-latest.json"
$settlementJson = Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.json"
$creditJson = Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.json"
$plannerJson = Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.json"
$envJson = Join-Path $astro "ASTRODDS-328-env-autofinder-loader-latest.json"

$dataset = Get-JsonSafe $datasetJson
$settlement = Get-JsonSafe $settlementJson
$credit = Get-JsonSafe $creditJson
$planner = Get-JsonSafe $plannerJson
$envDoc = Get-JsonSafe $envJson

$envFound = JVal $envDoc @("envFound") "False"
$creditStatus = JVal $credit @("status","Status") "UNKNOWN"
$ledgerPending = JVal $settlement @("pending","Pending") "UNKNOWN"
$ledgerSettled = JVal $settlement @("settled","Settled") "UNKNOWN"
$trainingLabeledRows = JVal $dataset @("labeledSettledRows","LabeledSettledRows") "UNKNOWN"
$plannerOk = if ($null -ne $planner) { "True" } else { "False" }

$blocks = @()
$warn = @()

if (!(Test-Path $client)) { $blocks += "client report missing" }
if (!(Test-Path $admin)) { $blocks += "admin report missing" }
if ($envFound -ne "True") { $blocks += ".env not found by autofinder" }
if ($plannerOk -ne "True") { $blocks += "smart scan planner missing" }
if ($null -eq $settlement) { $blocks += "settlement integrity report missing" }
if ($null -eq $dataset) { $blocks += "training dataset report missing" }

if ($ledgerPending -ne "UNKNOWN") {
    try { if ([int]$ledgerPending -gt 0) { $warn += "ledger has pending picks: $ledgerPending" } } catch {}
}

if ($trainingLabeledRows -ne "UNKNOWN") {
    try { if ([int]$trainingLabeledRows -lt 1) { $warn += "training labeled rows still 0" } } catch {}
}

if ($creditStatus -ne "OK") { $warn += "credit dashboard status: $creditStatus" }

$status = "READY_100_LOCAL_TEST_MODE"
if ($blocks.Count -gt 0) { $status = "NOT_READY_BLOCKED" }
elseif ($warn.Count -gt 0) { $status = "READY_WITH_WARNINGS" }

$lines = @()
$lines += "ASTRODDS 352B FINAL 100% READINESS REPORT - DISPLAY FIX"
$lines += ""
$lines += "Status: $status"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "CORE"
$lines += "- One command: npm run astrodds"
$lines += "- Server/autopilot: local mode"
$lines += "- Env auto-load: $envFound"
$lines += "- Smart planner: $plannerOk"
$lines += "- Credit guard: $creditStatus"
$lines += "- Ledger pending: $ledgerPending"
$lines += "- Ledger settled: $ledgerSettled"
$lines += "- Training labeled rows: $trainingLabeledRows"
$lines += ""
$lines += "HARD BLOCKS"
if ($blocks.Count -eq 0) { $lines += "- none" } else { foreach ($b in $blocks) { $lines += "- $b" } }
$lines += ""
$lines += "WARNINGS"
if ($warn.Count -eq 0) { $lines += "- none" } else { foreach ($w in $warn) { $lines += "- $w" } }
$lines += ""
$lines += "VERDICT"
if ($status -eq "READY_100_LOCAL_TEST_MODE") {
    $lines += "- ASTRODDS is 100% ready for local production-safe testing."
    $lines += "- Keep Telegram dry-run until one or two more clean slates are verified."
    $lines += "- The system is not yet statistically proven; it needs more settled picks."
} elseif ($status -eq "READY_WITH_WARNINGS") {
    $lines += "- ASTRODDS can run, but review warnings before claiming it is fully clean."
} else {
    $lines += "- Do not leave unattended until hard blocks are fixed."
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    hardBlocks=@($blocks)
    warnings=@($warn)
    envFound=$envFound
    plannerOk=$plannerOk
    creditStatus=$creditStatus
    ledgerPending=$ledgerPending
    ledgerSettled=$ledgerSettled
    trainingLabeledRows=$trainingLabeledRows
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
