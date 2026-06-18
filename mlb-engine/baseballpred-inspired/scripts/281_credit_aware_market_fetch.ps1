$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro
Load-EnvLocal $root

$outCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-281-credit-aware-market-fetch-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-281-credit-aware-market-fetch-latest.json"
$creditCsv = Join-Path $astro "ASTRODDS-odds-api-credit-ledger-latest.csv"
$creditJson = Join-Path $astro "ASTRODDS-odds-api-credit-ledger-latest.json"

Write-Host ""
Write-Host "ASTRODDS 281 CREDIT-AWARE MARKET FETCH" -ForegroundColor Cyan
Write-Host "Only calls Odds API if credit guard allows it." -ForegroundColor Cyan
Write-Host ""


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

function Game-Key($game) {
    $g = "$game"
    $awayTeamName = ""
    $homeTeamName = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }

    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
}

$monthlyLimit = 500
$reserve = 60
$maxDaily = 8
try { if ($env:ASTRODDS_ODDS_MONTHLY_LIMIT) { $monthlyLimit = [int]$env:ASTRODDS_ODDS_MONTHLY_LIMIT } } catch {}
try { if ($env:ASTRODDS_ODDS_RESERVE) { $reserve = [int]$env:ASTRODDS_ODDS_RESERVE } } catch {}
try { if ($env:ASTRODDS_ODDS_MAX_DAILY) { $maxDaily = [int]$env:ASTRODDS_ODDS_MAX_DAILY } } catch {}

$now = Get-Date
$monthKey = $now.ToString("yyyy-MM")
$dayKey = $now.ToString("yyyy-MM-dd")

$ledger = Safe-Csv $creditCsv
$monthRows = @($ledger | Where-Object { (Get-Val $_ @("MonthKey")) -eq $monthKey })
$dayRows = @($ledger | Where-Object { (Get-Val $_ @("DayKey")) -eq $dayKey -and (Get-Val $_ @("ApiCalled")) -eq "YES" })

$localMonthCost = 0
foreach ($r in $monthRows) {
    $c = Num (Get-Val $r @("RequestsLast","EstimatedCost"))
    if ($null -ne $c) { $localMonthCost += [int][math]::Round($c,0) }
}

$apiAllowed = $true
$guardReasons = @()

if (-not $env:ODDS_API_KEY) {
    $apiAllowed = $false
    $guardReasons += "missing ODDS_API_KEY"
}

if ($localMonthCost -ge ($monthlyLimit - $reserve)) {
    $apiAllowed = $false
    $guardReasons += "monthly local usage $localMonthCost reached limit-reserve $($monthlyLimit-$reserve)"
}

if ($dayRows.Count -ge $maxDaily) {
    $apiAllowed = $false
    $guardReasons += "daily odds calls $($dayRows.Count) reached maxDaily $maxDaily"
}

# Time gap guard: avoid repeated calls within 20 minutes unless FORCE.
$lastCall = @($ledger | Where-Object { (Get-Val $_ @("ApiCalled")) -eq "YES" } | Sort-Object FetchedAt -Descending | Select-Object -First 1)
if ($lastCall.Count -gt 0 -and -not $env:ASTRODDS_FORCE_ODDS_CALL) {
    try {
        $lastTime = [datetime](Get-Val $lastCall[0] @("FetchedAt"))
        $minutesAgo = ($now - $lastTime).TotalMinutes
        if ($minutesAgo -lt 20) {
            $apiAllowed = $false
            $guardReasons += "last odds API call was $([math]::Round($minutesAgo,1)) minutes ago; min gap is 20"
        }
    } catch {}
}

$rows = @()
$rawMeta = @()
$headers = @{}
$apiCalled = "NO"
$status = "FALLBACK_ONLY"
$requestsLast = 0
$requestsUsed = ""
$requestsRemaining = ""

function Add-Market-Row($source, $game, $awayTeamName, $homeTeamName, $pick, $prob, $priceText, $book, $url) {
    $p = Num $prob
    if ($null -eq $p) { return }
    if ($p -gt 1) { $p = $p / 100.0 }
    if ($p -le 0 -or $p -ge 1) { return }

    $script:rows += ,[pscustomobject]@{
        Source = $source
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        Game = $game
        AwayTeam = $awayTeamName
        HomeTeam = $homeTeamName
        Pick = $pick
        MarketType = "MONEYLINE"
        MarketProbability = [math]::Round($p, 6)
        Entry = ([math]::Round($p * 100.0, 1)).ToString() + "¢"
        PriceText = $priceText
        Bookmaker = $book
        SourceUrl = $url
        FetchedAt = (Get-Date).ToString("o")
    }
}

if ($apiAllowed) {
    $url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?regions=us&markets=h2h&oddsFormat=decimal&apiKey=$($env:ODDS_API_KEY)"
    try {
        $resp = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 30
        $apiCalled = "YES"
        $status = "ODDS_API_CONNECTED"
        $headers = $resp.Headers
        try { $requestsLast = [int]$headers["x-requests-last"] } catch { $requestsLast = 1 }
        try { $requestsUsed = "$($headers["x-requests-used"])" } catch {}
        try { $requestsRemaining = "$($headers["x-requests-remaining"])" } catch {}

        $odds = $resp.Content | ConvertFrom-Json
        foreach ($event in @($odds)) {
            $awayTeamName = "$($event.away_team)"
            $homeTeamName = "$($event.home_team)"
            $game = "$awayTeamName @ $homeTeamName"

            foreach ($bm in @($event.bookmakers)) {
                $book = "$($bm.title)"
                foreach ($market in @($bm.markets)) {
                    if ("$($market.key)" -ne "h2h") { continue }
                    foreach ($outcome in @($market.outcomes)) {
                        $name = "$($outcome.name)"
                        $decimal = Num "$($outcome.price)"
                        if ($null -ne $decimal -and $decimal -gt 1) {
                            $implied = 1.0 / $decimal
                            Add-Market-Row "THE_ODDS_API_H2H" $game $awayTeamName $homeTeamName $name $implied "$decimal decimal" $book $url
                        }
                    }
                }
            }
        }
    } catch {
        $apiCalled = "NO"
        $status = "ODDS_API_ERROR_FALLBACK_ONLY"
        $guardReasons += "Odds API error: $($_.Exception.Message)"
    }
} else {
    $status = "CREDIT_GUARD_BLOCKED_FALLBACK_ONLY"
}

# Fallback internal market rows always included.
$control = Safe-Csv (Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv")
$guard = Safe-Csv (Join-Path $astro "ASTRODDS-249-price-guard-latest.csv")

foreach ($r in $control) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $price = Get-Val $r @("MarketProbability","Price")
    if ($game -eq "" -or $pick -eq "" -or $price -eq "") { continue }
    $parts = $game -split "\s@\s", 2
    $awayTeamName = if ($parts.Count -ge 1) { $parts[0] } else { "" }
    $homeTeamName = if ($parts.Count -ge 2) { $parts[1] } else { "" }
    Add-Market-Row "ASTRODDS_CONTROL_BOARD_EXISTING" $game $awayTeamName $homeTeamName $pick $price "$price" "internal" ""
}

foreach ($r in $guard) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $price = Get-Val $r @("CurrentEntry","Entry")
    if ($game -eq "" -or $pick -eq "" -or $price -eq "") { continue }
    $parts = $game -split "\s@\s", 2
    $awayTeamName = if ($parts.Count -ge 1) { $parts[0] } else { "" }
    $homeTeamName = if ($parts.Count -ge 2) { $parts[1] } else { "" }
    Add-Market-Row "ASTRODDS_PRICE_GUARD_EXISTING" $game $awayTeamName $homeTeamName $pick $price "$price" "internal" ""
}

# Deduplicate
$dedup = @{}
$out = @()
foreach ($r in $rows) {
    $k = (Game-Key (Get-Val $r @("Game"))) + "|" + (Normalize-Team (Get-Val $r @("Pick"))) + "|" + (Get-Val $r @("Source")) + "|" + (Get-Val $r @("Bookmaker"))
    if (-not $dedup.ContainsKey($k)) {
        $dedup[$k] = $true
        $out += ,$r
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$externalRows = @($out | Where-Object { (Get-Val $_ @("Source")) -like "THE_ODDS_API*" }).Count
$internalRows = @($out | Where-Object { (Get-Val $_ @("Source")) -like "ASTRODDS*" }).Count

$newLedgerRow = [pscustomobject]@{
    FetchedAt = (Get-Date).ToString("o")
    MonthKey = $monthKey
    DayKey = $dayKey
    ApiCalled = $apiCalled
    Status = $status
    RequestsLast = $requestsLast
    RequestsUsedHeader = $requestsUsed
    RequestsRemainingHeader = $requestsRemaining
    EstimatedCost = if ($apiCalled -eq "YES") { 1 } else { 0 }
    MonthlyLocalCostBefore = $localMonthCost
    DailyCallsBefore = $dayRows.Count
    ExternalRows = $externalRows
    InternalRows = $internalRows
    GuardReasons = ($guardReasons -join " | ")
}

$allLedger = @($ledger) + @($newLedgerRow)
$allLedger | Export-Csv -NoTypeInformation -Encoding UTF8 $creditCsv
Write-Json $allLedger $creditJson

$lines = @()
$lines += "ASTRODDS 281 CREDIT-AWARE MARKET FETCH"
$lines += ""
$lines += "Status: $status"
$lines += "API called: $apiCalled"
$lines += "Monthly local cost before call: $localMonthCost / $monthlyLimit"
$lines += "Reserve: $reserve"
$lines += "Daily calls before call: $($dayRows.Count) / $maxDaily"
$lines += "Requests last header: $requestsLast"
$lines += "Requests used header: $requestsUsed"
$lines += "Requests remaining header: $requestsRemaining"
$lines += "Market rows total: $($out.Count)"
$lines += "External odds rows: $externalRows"
$lines += "Internal fallback rows: $internalRows"
if ($guardReasons.Count -gt 0) { $lines += "Guard reasons: $($guardReasons -join ' | ')" }
$lines += ""
$lines += "Output: $outCsv"
$lines += "Credit ledger: $creditCsv"
$lines += ""
$lines += "Sample:"
foreach ($r in ($out | Select-Object -First 10)) {
    $lines += "- $($r.Source) | $($r.Pick) | $($r.Game) | Entry=$($r.Entry) | Book=$($r.Bookmaker)"
}

Write-Json $newLedgerRow $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
