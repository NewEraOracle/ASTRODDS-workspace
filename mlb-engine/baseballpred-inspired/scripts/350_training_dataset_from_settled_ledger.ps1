$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) } catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        try {
            $p = $row.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return ""
}

function Set-Prop($obj, $name, $value) {
    if ($obj.PSObject.Properties[$name]) {
        $obj.$name = $value
    } else {
        $obj | Add-Member -MemberType NoteProperty -Name $name -Value $value -Force
    }
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) { return $n }
    return $null
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exit = $LASTEXITCODE
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exit"
        $childLog.Value += "DURATION: $dur sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
        } else {
            Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
        }
    } catch {
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-model-training-dataset-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-350-training-dataset-from-settled-ledger-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-350-training-dataset-from-settled-ledger-latest.json"

Write-Host ""
Write-Host "ASTRODDS 350 TRAINING DATASET FROM SETTLED LEDGER" -ForegroundColor Cyan
Write-Host "Fixes labeled settled rows by reading ledger SETTLED + WIN/LOSS directly." -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
$out = @()

foreach ($r in $ledger) {
    $status = Get-Val $r @("Status")
    $result = (Get-Val $r @("Result")).ToUpper()
    $label = ""

    if ($status -eq "SETTLED" -and $result -eq "WIN") { $label = "1" }
    elseif ($status -eq "SETTLED" -and $result -eq "LOSS") { $label = "0" }

    $modelRaw = Get-Val $r @("FullSlateModel","PublicModel","ModelProbability","Model")
    $entryRaw = Get-Val $r @("EntryPrice","Entry","BestEntry")
    $edgeRaw = Get-Val $r @("Edge","EdgeVsBest")

    $out += ,[pscustomobject]@{
        Label = $label
        Status = $status
        Result = $result
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        ScheduleDate = Get-Val $r @("ScheduleDate")
        GamePk = Get-Val $r @("GamePk")
        Winner = Get-Val $r @("Winner")
        FinalScore = Get-Val $r @("FinalScore")
        EntryPrice = $entryRaw
        ModelProbability = $modelRaw
        Edge = $edgeRaw
        ROI = Get-Val $r @("ROI")
        CLV = Get-Val $r @("CLV")
        BrierComponent = Get-Val $r @("BrierComponent")
        LogLossComponent = Get-Val $r @("LogLossComponent")
        SourceGate = Get-Val $r @("SourceGate")
        LoggedAt = Get-Val $r @("LoggedAt")
        SettledAt = Get-Val $r @("SettledAt")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$labeled = @($out | Where-Object { "$($_.Label)" -ne "" })
$wins = @($labeled | Where-Object { $_.Label -eq "1" }).Count
$losses = @($labeled | Where-Object { $_.Label -eq "0" }).Count
$pending = @($out | Where-Object { $_.Status -eq "PENDING_RESULT" }).Count

$lines = @()
$lines += "ASTRODDS 350 TRAINING DATASET FROM SETTLED LEDGER"
$lines += ""
$lines += "Ledger rows: $($ledger.Count)"
$lines += "Training dataset rows: $($out.Count)"
$lines += "Labeled settled rows: $($labeled.Count)"
$lines += "Wins: $wins"
$lines += "Losses: $losses"
$lines += "Pending rows: $pending"
$lines += "Output: $outCsv"
$lines += ""
$lines += "ROWS"
foreach ($r in $out) {
    $lines += "- label=$($r.Label) | $($r.Result) | $($r.Pick) | $($r.Game) | ROI=$($r.ROI)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    ledgerRows=$ledger.Count
    datasetRows=$out.Count
    labeledSettledRows=$labeled.Count
    wins=$wins
    losses=$losses
    pending=$pending
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
