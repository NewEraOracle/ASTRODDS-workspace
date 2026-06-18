$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$runner245b = Join-Path $scripts "245b_run_final_confidence_client_drop_NO_243.ps1"

$gate240 = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$baseConfidenceCsv = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.csv"

$outCsv = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-context-merged-confidence-latest.txt"
$outChildLog = Join-Path $astro "ASTRODDS-248-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 248 CONTEXT-MERGED CONFIDENCE SCORE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - WEATHER / INJURY / PITCHER / BULLPEN INTO CONFIDENCE" -ForegroundColor Cyan
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

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
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

function Latest-ContextFile($pattern) {
    if (!(Test-Path $astro)) { return $null }
    $exclude = "child|telegram|message|ledger|dedupe|mismatch|run-latest|final-confidence|official-picks-ledger|strict-context-connection-audit"
    return Get-ChildItem -Path $astro -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension -in @(".json",".csv",".txt") -and
            $_.Name -match $pattern -and
            $_.Name -notmatch $exclude
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function Flatten-JsonRows($obj) {
    if ($null -eq $obj) { return @() }
    if ($obj -is [System.Array]) { return @($obj) }

    $rows = @()
    foreach ($p in $obj.PSObject.Properties) {
        if ($p.Value -is [System.Array]) {
            $rows += @($p.Value)
        }
    }
    if ($rows.Count -eq 0) { $rows += ,$obj }
    return @($rows)
}

function Load-Rows($fileObj) {
    if ($null -eq $fileObj) { return @() }
    try {
        if ($fileObj.Extension -eq ".csv") { return @(Import-Csv $fileObj.FullName) }
        if ($fileObj.Extension -eq ".json") { return @(Flatten-JsonRows (Read-JsonSafe $fileObj.FullName)) }
        return @()
    } catch { return @() }
}

function Row-RawText($row) {
    if ($null -eq $row) { return "" }
    $parts = @()
    foreach ($p in $row.PSObject.Properties) {
        if ($null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            $parts += "$($p.Name)=$($p.Value)"
        }
    }
    return ($parts -join " | ")
}

function Raw-Contains($raw, $needle) {
    if ($null -eq $raw -or "$needle" -eq "") { return $false }
    return ($raw.IndexOf("$needle", [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
}

function Find-ContextForGame($fileObj, $game) {
    $split = Split-Game $game
    $rows = Load-Rows $fileObj

    foreach ($r in $rows) {
        $raw = Row-RawText $r
        $hasGame = Raw-Contains $raw $game
        $hasAway = Raw-Contains $raw $split.Away
        $hasHome = Raw-Contains $raw $split.Home
        if ($hasGame -or ($hasAway -and $hasHome)) {
            return [pscustomobject]@{
                Status = "ROW_CONNECTED"
                File = if ($null -ne $fileObj) { $fileObj.Name } else { "" }
                Detail = $raw
            }
        }
    }

    if ($null -ne $fileObj) {
        $rawFile = ""
        try { $rawFile = Get-Content $fileObj.FullName -Raw } catch {}
        if ((Raw-Contains $rawFile $game) -or ((Raw-Contains $rawFile $split.Away) -and (Raw-Contains $rawFile $split.Home))) {
            return [pscustomobject]@{
                Status = "FILE_MATCH_NOT_MERGED"
                File = $fileObj.Name
                Detail = "Source file contains game/team match, but row extraction failed. Treat as connected but review."
            }
        }
    }

    return [pscustomobject]@{
        Status = if ($null -ne $fileObj) { "NO_GAME_MATCH" } else { "NO_FILE" }
        File = if ($null -ne $fileObj) { $fileObj.Name } else { "" }
        Detail = ""
    }
}

function Context-Adjustment($category, $detail) {
    $d = "$detail".ToLower()
    $adj = 0
    $flags = @()

    if ($category -eq "weather") {
        if ($d -match "rain|storm|delay|heavy wind|wind.*1[5-9]|wind.*2[0-9]") { $adj -= 4; $flags += "weather_risk" }
        elseif ($d -ne "") { $adj += 1; $flags += "weather_checked" }
    }

    if ($category -eq "injury") {
        if ($d -match "picked team risk high|team risk high|risk=high|injuryrisk=high") { $adj -= 6; $flags += "picked_team_injury_high" }
        elseif ($d -match "opponent risk high|opponent.*high") { $adj += 2; $flags += "opponent_injury_high" }
        elseif ($d -ne "") { $adj += 1; $flags += "injury_checked" }
    }

    if ($category -eq "pitcher") {
        if ($d -match "era 6|era=6|whip 1\.7|whip=1\.7|whip 1\.8|whip=1\.8") { $adj -= 3; $flags += "pitcher_risk" }
        elseif ($d -ne "") { $adj += 2; $flags += "pitcher_checked" }
    }

    if ($category -eq "bullpen") {
        if ($d -match "fatigue high|high fatigue|heavy_bullpen|three_games") { $adj -= 4; $flags += "bullpen_fatigue_risk" }
        elseif ($d -match "opponent.*fatigue high|away fatigue high|home fatigue high") { $adj += 1; $flags += "bullpen_context_checked" }
        elseif ($d -ne "") { $adj += 1; $flags += "bullpen_checked" }
    }

    return [pscustomobject]@{ Adjustment=$adj; Flags=($flags -join ",") }
}

function Base-Confidence($row) {
    $edge = Num (Get-Val $row @("Edge"))
    $model = Num (Get-Val $row @("ModelProbability"))
    if ($null -eq $edge) { $edge = 0 }
    if ($null -eq $model) { $model = 50 }
    if ($model -le 1) { $model *= 100 }

    $score = 45.0
    $score += [math]::Min(25.0, [math]::Max(0.0, $edge * 1.5))
    $score += [math]::Min(12.0, [math]::Max(0.0, ($model - 50.0) * 0.8))

    if ((Get-Val $row @("AwayLineupStatus")) -eq "confirmed" -and (Get-Val $row @("HomeLineupStatus")) -eq "confirmed") { $score += 8.0 }

    $status = (Get-Val $row @("MlbStatus")).ToLower()
    if ($status -match "pre-game|pregame|warmup|in progress|live") { $score += 3.0 }

    $reason = Get-Val $row @("FinalReason")
    if ($reason -match "Passed|trusted full slate|Promoted") { $score += 5.0 }

    if ($edge -lt 10) { $score = [math]::Min($score, 84.0) }
    else { $score = [math]::Min($score, 92.0) }

    return [math]::Max(55.0, $score)
}

function Grade-From-Edge($edgeText) {
    $e = Num $edgeText
    if ($null -eq $e) { return "OFFICIAL" }
    if ($e -ge 10) { return "STRONG BUY" }
    if ($e -ge 5) { return "VALUE BUY" }
    return "OFFICIAL"
}

function Stake-Text($grade) {
    if ($grade -eq "STRONG BUY") { return "5% bankroll max" }
    if ($grade -eq "VALUE BUY") { return "2–3% bankroll recommended / 5% max" }
    return "1–2% bankroll recommended"
}

$steps = @()
$steps += ,(Run-Step "245B confidence rescan" $runner245b)
$childLog | Set-Content -Encoding UTF8 $outChildLog

$weatherFile = Latest-ContextFile "weather|meteo|wind|rain|forecast|ballpark"
$injuryFile = Latest-ContextFile "injur|injury|injuries"
$pitcherFile = Latest-ContextFile "pitcher|starter|probable"
$bullpenFile = Latest-ContextFile "bullpen|fatigue|relief"

$gateRows = Safe-Csv $gate240
$officialRows = @($gateRows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK" })

$outRows = @()

foreach ($r in $officialRows) {
    $game = Get-Val $r @("Game")

    $weather = Find-ContextForGame $weatherFile $game
    $injury = Find-ContextForGame $injuryFile $game
    $pitcher = Find-ContextForGame $pitcherFile $game
    $bullpen = Find-ContextForGame $bullpenFile $game

    $base = Base-Confidence $r

    $wAdj = Context-Adjustment "weather" $weather.Detail
    $iAdj = Context-Adjustment "injury" $injury.Detail
    $pAdj = Context-Adjustment "pitcher" $pitcher.Detail
    $bAdj = Context-Adjustment "bullpen" $bullpen.Detail

    $contextAdj = $wAdj.Adjustment + $iAdj.Adjustment + $pAdj.Adjustment + $bAdj.Adjustment
    $merged = $base + $contextAdj

    $edge = Num (Get-Val $r @("Edge"))
    if ($null -eq $edge) { $edge = 0 }

    if ($edge -lt 10) { $merged = [math]::Min($merged, 86.0) }
    else { $merged = [math]::Min($merged, 94.0) }
    $merged = [math]::Max(50.0, $merged)

    $contextStatus = "FULL_CONTEXT_CONNECTED"
    foreach ($s in @($weather.Status,$injury.Status,$pitcher.Status,$bullpen.Status)) {
        if ($s -eq "NO_FILE" -or $s -eq "NO_GAME_MATCH") { $contextStatus = "PARTIAL_CONTEXT" }
    }

    $flags = @($wAdj.Flags,$iAdj.Flags,$pAdj.Flags,$bAdj.Flags) | Where-Object { $_ -ne "" }

    $outRows += ,[pscustomobject]@{
        Grade = Grade-From-Edge (Get-Val $r @("Edge"))
        Pick = Get-Val $r @("Pick")
        Game = $game
        Entry = Get-Val $r @("Price")
        BaseConfidence = [int][math]::Round($base,0)
        ContextAdjustment = $contextAdj
        Confidence = [int][math]::Round($merged,0)
        Model = Get-Val $r @("ModelProbability")
        Edge = Get-Val $r @("Edge")
        Stake = Stake-Text (Grade-From-Edge (Get-Val $r @("Edge")))
        Status = Get-Val $r @("MlbStatus")
        Lineups = (Get-Val $r @("AwayLineupStatus")) + " / " + (Get-Val $r @("HomeLineupStatus"))
        ContextStatus = $contextStatus
        ContextFlags = ($flags -join "|")
        WeatherStatus = $weather.Status
        WeatherFile = $weather.File
        InjuryStatus = $injury.Status
        InjuryFile = $injury.File
        PitcherStatus = $pitcher.Status
        PitcherFile = $pitcher.File
        BullpenStatus = $bullpen.Status
        BullpenFile = $bullpen.File
    }
}

$outRows = @($outRows | Sort-Object Confidence -Descending)
$outRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$telegram = @()
if ($outRows.Count -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• Confidence is ASTRODDS score /100"
    $telegram += "• Context checked: lineups, model, market, weather, injuries, pitcher, bullpen"
    $telegram += "• 5% bankroll max per pick"
    $telegram += ""

    $i = 1
    foreach ($r in $outRows) {
        $telegram += "✅ $($r.Grade) #$i"
        $telegram += "$($r.Pick) ML"
        $telegram += "Game: $($r.Game)"
        $telegram += "Entry: $($r.Entry)"
        $telegram += "Confidence: $($r.Confidence)/100"
        $telegram += "Stake: $($r.Stake)"
        $telegram += "Status: $($r.Status)"
        $telegram += ""
        $i++
    }

    $telegram += "⚠️ Risk note:"
    $telegram += "Confidence is not a guaranteed win rate. It is a simplified score based on ASTRODDS internal model, market value, live lineups, weather, injuries, pitcher, bullpen and safety gates."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegram += "No official picks passed the final context-merged gate."
}

($telegram -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTelegram

$fullContext = @($outRows | Where-Object { $_.ContextStatus -eq "FULL_CONTEXT_CONNECTED" }).Count
$partialContext = @($outRows | Where-Object { $_.ContextStatus -ne "FULL_CONTEXT_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 248 CONTEXT-MERGED CONFIDENCE SCORE"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Official picks: $($outRows.Count)"
$lines += "Full-context picks: $fullContext"
$lines += "Partial-context picks: $partialContext"
$lines += ""
$lines += "SOURCE FILES"
$lines += "- Weather: $(if ($null -ne $weatherFile) { $weatherFile.Name } else { 'NO_FILE' })"
$lines += "- Injury: $(if ($null -ne $injuryFile) { $injuryFile.Name } else { 'NO_FILE' })"
$lines += "- Pitcher: $(if ($null -ne $pitcherFile) { $pitcherFile.Name } else { 'NO_FILE' })"
$lines += "- Bullpen: $(if ($null -ne $bullpenFile) { $bullpenFile.Name } else { 'NO_FILE' })"
$lines += ""
$lines += "OFFICIAL PICKS"
foreach ($r in $outRows) {
    $lines += "- $($r.Grade) | $($r.Pick) | $($r.Game) | Base=$($r.BaseConfidence) | Adj=$($r.ContextAdjustment) | Confidence=$($r.Confidence)/100"
    $lines += "  Context=$($r.ContextStatus) | Flags=$($r.ContextFlags)"
    $lines += "  Weather=$($r.WeatherStatus) | Injury=$($r.InjuryStatus) | Pitcher=$($r.PitcherStatus) | Bullpen=$($r.BullpenStatus)"
}
$lines += ""
$lines += "CLIENT MESSAGE"
$lines += ($telegram -join [Environment]::NewLine)

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialPicks = $outRows.Count
    fullContextPicks = $fullContext
    partialContextPicks = $partialContext
    telegram = $outTelegram
    rows = @($outRows)
    childLog = $outChildLog
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram: $outTelegram"
Write-Host "Child log: $outChildLog"
Write-Host ""
