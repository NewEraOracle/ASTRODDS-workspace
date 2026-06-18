$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$runner245b = Join-Path $scripts "245b_run_final_confidence_client_drop_NO_243.ps1"

$finalGate = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$controlBoard = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"
$confidenceCsv = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.csv"
$confidenceTxt = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.txt"

$outTxt = Join-Path $astro "ASTRODDS-247-strict-context-connection-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-247-strict-context-connection-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-247-strict-context-connection-audit-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-247-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 247 STRICT CONTEXT CONNECTION AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - NO FALSE POSITIVE WEATHER / INJURY / PITCHER / BULLPEN" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{ Name=$name; Status="MISSING"; ExitCode=""; DurationSec=0 }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{ Name=$name; Status="OK"; ExitCode="0"; DurationSec=$duration }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="$exitCode"; DurationSec=$duration }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"
        return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="1"; DurationSec=$duration }
    }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
    }
    return ""
}

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Game($game) {
    $awayTeamName = ""
    $homeTeamName = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    }

    return [pscustomobject]@{
        Away = $awayTeamName
        Home = $homeTeamName
        Key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
    }
}

function Find-Row-By-Game($rows, $game) {
    $target = (Split-Game $game).Key

    foreach ($r in $rows) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }

        if ((Split-Game $g).Key -eq $target) {
            return $r
        }
    }

    return $null
}

function Field-Matches($fieldName, $category) {
    $k = "$fieldName".ToLower()

    if ($category -eq "weather") {
        return (
            $k -like "*weather*" -or
            $k -like "*wind*" -or
            $k -like "*temperature*" -or
            $k -like "*temp*" -or
            $k -like "*rain*" -or
            $k -like "*precip*" -or
            $k -like "*roof*" -or
            $k -like "*humidity*" -or
            $k -like "*ballparkweather*"
        )
    }

    if ($category -eq "injury") {
        return (
            $k -like "*injury*" -or
            $k -like "*injuries*" -or
            $k -like "*injured*" -or
            $k -like "*injuryrisk*" -or
            $k -like "*injurydetail*" -or
            $k -eq "il" -or
            $k -like "*ilstatus*"
        )
    }

    if ($category -eq "pitcher") {
        return (
            $k -like "*pitcher*" -or
            $k -like "*starter*" -or
            $k -like "*probable*" -or
            $k -like "*whip*" -or
            $k -like "*starterera*" -or
            $k -like "*pitcherera*" -or
            $k -like "*era_*" -or
            $k -like "*_era" -or
            $k -eq "era"
        )
    }

    if ($category -eq "bullpen") {
        return (
            $k -like "*bullpen*" -or
            $k -like "*reliever*" -or
            $k -like "*relief*" -or
            $k -like "*fatigue*"
        )
    }

    if ($category -eq "market") {
        return (
            $k -like "*market*" -or
            $k -like "*price*" -or
            $k -like "*odds*" -or
            $k -like "*entry*"
        )
    }

    return $false
}

function Get-Strict-Fields($row, $category) {
    if ($null -eq $row) { return "" }

    $hits = @()

    foreach ($p in $row.PSObject.Properties) {
        $name = "$($p.Name)"
        $value = ""
        if ($null -ne $p.Value) { $value = "$($p.Value)".Trim() }
        if ($value -eq "") { continue }

        if (Field-Matches $name $category) {
            $hits += "$name=$value"
        }
    }

    return ($hits -join " | ")
}

function Latest-ContextFile($pattern) {
    if (!(Test-Path $astro)) { return $null }

    $exclude = "child|telegram|message|ledger|dedupe|mismatch|audit-latest|run-latest|final-confidence|official-picks-ledger"

    $f = Get-ChildItem -Path $astro -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension -in @(".json",".csv") -and
            $_.Name -match $pattern -and
            $_.Name -notmatch $exclude
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    return $f
}

function Raw-Contains($raw, $needle) {
    if ($null -eq $raw -or $null -eq $needle -or "$needle" -eq "") { return $false }
    return ($raw.IndexOf("$needle", [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
}

function Get-Context-Source-Status($fileObj, $game, $rowFields) {
    if ($rowFields -ne "") {
        return [pscustomobject]@{
            Status = "ROW_CONNECTED"
            File = if ($null -ne $fileObj) { "$($fileObj.Name)" } else { "" }
            FileTime = if ($null -ne $fileObj) { "$($fileObj.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))" } else { "" }
            Detail = $rowFields
        }
    }

    if ($null -eq $fileObj) {
        return [pscustomobject]@{
            Status = "NO_FILE_FOUND"
            File = ""
            FileTime = ""
            Detail = ""
        }
    }

    $split = Split-Game $game
    $raw = ""
    try { $raw = Get-Content $fileObj.FullName -Raw }
    catch { $raw = "" }

    $hasAway = Raw-Contains $raw $split.Away
    $hasHome = Raw-Contains $raw $split.Home
    $hasGame = Raw-Contains $raw $game

    if ($hasGame -or ($hasAway -and $hasHome)) {
        return [pscustomobject]@{
            Status = "FILE_MATCH_NOT_MERGED"
            File = "$($fileObj.Name)"
            FileTime = "$($fileObj.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
            Detail = "Source file contains game/team match, but fields are not merged into official pick row."
        }
    }

    if ($hasAway -or $hasHome) {
        return [pscustomobject]@{
            Status = "PARTIAL_TEAM_MATCH"
            File = "$($fileObj.Name)"
            FileTime = "$($fileObj.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
            Detail = "Source file contains one team only. Needs review before use."
        }
    }

    return [pscustomobject]@{
        Status = "FILE_EXISTS_NO_GAME_MATCH"
        File = "$($fileObj.Name)"
        FileTime = "$($fileObj.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
        Detail = "File exists but this game was not found."
    }
}

$steps = @()
$steps += ,(Run-Step "245B full confidence rescan" $runner245b)
$childLog | Set-Content -Encoding UTF8 $outChildLog

$finalRows = Safe-Csv $finalGate
$controlRows = Safe-Csv $controlBoard
$confidenceRows = Safe-Csv $confidenceCsv

$weatherFile = Latest-ContextFile "weather|meteo|wind|rain|forecast|ballpark"
$injuryFile = Latest-ContextFile "injur|injury|injuries"
$pitcherFile = Latest-ContextFile "pitcher|starter|probable"
$bullpenFile = Latest-ContextFile "bullpen|fatigue|relief"

$officialRows = @($finalRows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK" })
$reviewRows = @($finalRows | Where-Object { (Get-Val $_ @("FinalDecision")) -like "REVIEW*" })
$blockedRows = @($finalRows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW" })

$auditRows = @()

foreach ($r in $officialRows) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $control = Find-Row-By-Game $controlRows $game

    $weatherFields = Get-Strict-Fields $control "weather"
    $injuryFields = Get-Strict-Fields $control "injury"
    $pitcherFields = Get-Strict-Fields $control "pitcher"
    $bullpenFields = Get-Strict-Fields $control "bullpen"
    $marketFields = Get-Strict-Fields $control "market"

    $weatherStatus = Get-Context-Source-Status $weatherFile $game $weatherFields
    $injuryStatus = Get-Context-Source-Status $injuryFile $game $injuryFields
    $pitcherStatus = Get-Context-Source-Status $pitcherFile $game $pitcherFields
    $bullpenStatus = Get-Context-Source-Status $bullpenFile $game $bullpenFields

    $confidence = ""
    foreach ($c in $confidenceRows) {
        if ((Get-Val $c @("Pick")) -eq $pick -and (Get-Val $c @("Game")) -eq $game) {
            $confidence = Get-Val $c @("Confidence")
        }
    }

    $contextCompleteness = "PARTIAL_CONTEXT"
    if (
        $weatherStatus.Status -eq "ROW_CONNECTED" -and
        $injuryStatus.Status -eq "ROW_CONNECTED" -and
        $pitcherStatus.Status -eq "ROW_CONNECTED" -and
        $bullpenStatus.Status -eq "ROW_CONNECTED"
    ) {
        $contextCompleteness = "FULL_CONTEXT_CONNECTED"
    }

    $auditRows += ,[pscustomobject]@{
        Pick = $pick
        Game = $game
        FinalDecision = Get-Val $r @("FinalDecision")
        Entry = Get-Val $r @("Price")
        Confidence = $confidence
        Model = Get-Val $r @("ModelProbability")
        Edge = Get-Val $r @("Edge")
        MlbStatus = Get-Val $r @("MlbStatus")
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        WeatherStatus = $weatherStatus.Status
        WeatherFile = $weatherStatus.File
        WeatherDetail = $weatherStatus.Detail
        InjuryStatus = $injuryStatus.Status
        InjuryFile = $injuryStatus.File
        InjuryDetail = $injuryStatus.Detail
        PitcherStatus = $pitcherStatus.Status
        PitcherFile = $pitcherStatus.File
        PitcherDetail = $pitcherStatus.Detail
        BullpenStatus = $bullpenStatus.Status
        BullpenFile = $bullpenStatus.File
        BullpenDetail = $bullpenStatus.Detail
        MarketFields = $marketFields
        ContextCompleteness = $contextCompleteness
        FinalReason = Get-Val $r @("FinalReason")
    }
}

$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$fullContext = @($auditRows | Where-Object { $_.ContextCompleteness -eq "FULL_CONTEXT_CONNECTED" }).Count
$partialContext = @($auditRows | Where-Object { $_.ContextCompleteness -ne "FULL_CONTEXT_CONNECTED" }).Count

$clientText = ""
if (Test-Path $confidenceTxt) { $clientText = Get-Content $confidenceTxt -Raw }

$lines = @()
$lines += "ASTRODDS 247 STRICT CONTEXT CONNECTION AUDIT"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Official SEND_OK picks: $($officialRows.Count)"
$lines += "Review picks: $($reviewRows.Count)"
$lines += "Blocked picks: $($blockedRows.Count)"
$lines += "Full-context official picks: $fullContext"
$lines += "Partial-context official picks: $partialContext"
$lines += ""

$lines += "SOURCE FILES USED"
$lines += "- Weather: $(if ($null -ne $weatherFile) { $weatherFile.Name + ' | ' + $weatherFile.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'NO_FILE' })"
$lines += "- Injury: $(if ($null -ne $injuryFile) { $injuryFile.Name + ' | ' + $injuryFile.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'NO_FILE' })"
$lines += "- Pitcher: $(if ($null -ne $pitcherFile) { $pitcherFile.Name + ' | ' + $pitcherFile.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'NO_FILE' })"
$lines += "- Bullpen: $(if ($null -ne $bullpenFile) { $bullpenFile.Name + ' | ' + $bullpenFile.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'NO_FILE' })"
$lines += ""

$lines += "OFFICIAL PICK STRICT CONTEXT AUDIT"
foreach ($a in $auditRows) {
    $lines += "- $($a.Pick) | $($a.Game)"
    $lines += "  Entry=$($a.Entry) | Confidence=$($a.Confidence)/100 | Model=$($a.Model) | Edge=$($a.Edge) | Status=$($a.MlbStatus)"
    $lines += "  Lineups=$($a.AwayLineupStatus)/$($a.HomeLineupStatus)"
    $lines += "  Weather=$($a.WeatherStatus) | File=$($a.WeatherFile)"
    if ($a.WeatherDetail -ne "") { $lines += "    $($a.WeatherDetail)" }
    $lines += "  Injury=$($a.InjuryStatus) | File=$($a.InjuryFile)"
    if ($a.InjuryDetail -ne "") { $lines += "    $($a.InjuryDetail)" }
    $lines += "  Pitcher=$($a.PitcherStatus) | File=$($a.PitcherFile)"
    if ($a.PitcherDetail -ne "") { $lines += "    $($a.PitcherDetail)" }
    $lines += "  Bullpen=$($a.BullpenStatus) | File=$($a.BullpenFile)"
    if ($a.BullpenDetail -ne "") { $lines += "    $($a.BullpenDetail)" }
    $lines += "  MarketFields=$($a.MarketFields)"
    $lines += "  ContextCompleteness=$($a.ContextCompleteness)"
    $lines += "  Reason=$($a.FinalReason)"
}
$lines += ""

$lines += "DECISION"
if ($partialContext -gt 0) {
    $lines += "- Current picks are client-safe under the model/market/lineup gate."
    $lines += "- But they are not yet FULL BaseballPred-style context picks until weather/injury/pitcher/bullpen are merged directly into each official row."
    $lines += "- Next fix: 248 should merge strict weather/injury/pitcher/bullpen context into the confidence score."
} else {
    $lines += "- All official picks have full context connected."
}
$lines += ""

$lines += "CLIENT MESSAGE"
$lines += $clientText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialSendOk = $officialRows.Count
    review = $reviewRows.Count
    blocked = $blockedRows.Count
    fullContextOfficialPicks = $fullContext
    partialContextOfficialPicks = $partialContext
    officialAuditRows = @($auditRows)
    childLog = $outChildLog
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host ""
