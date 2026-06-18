$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-273-fetch-market-moneyline-sources-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 273 FETCH MARKET MONEYLINE SOURCES" -ForegroundColor Cyan
Write-Host "Optional source: The Odds API if ODDS_API_KEY exists. Fallback: existing ASTRODDS market files." -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 25 | Set-Content -Encoding UTF8 $path
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

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

$schedule = Safe-Csv $scheduleCsv
$rows = @()
$rawPayloads = @()

function Add-Market-Row($source, $game, $awayTeamName, $homeTeamName, $pick, $prob, $priceText, $book, $url) {
    if ($pick -eq "" -or $game -eq "") { return }

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

# 1) Optional The Odds API
$apiKey = $env:ODDS_API_KEY
if ($apiKey -ne "") {
    $url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?regions=us&markets=h2h&oddsFormat=decimal&apiKey=$apiKey"
    $odds = Invoke-Json $url 25
    $rawPayloads += ,[pscustomobject]@{ Source="THE_ODDS_API"; Url=$url; Payload=$odds }

    if ($null -ne $odds) {
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
    }
}

# 2) Fallback existing ASTRODDS files with control/guard price.
$control = Safe-Csv (Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv")
$guard = Safe-Csv (Join-Path $astro "ASTRODDS-249-price-guard-latest.csv")

foreach ($r in $control) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $price = Get-Val $r @("MarketProbability","Price")
    if ($game -eq "" -or $pick -eq "" -or $price -eq "") { continue }

    $teams = $game -split "\s@\s", 2
    $awayTeamName = if ($teams.Count -ge 1) { $teams[0] } else { "" }
    $homeTeamName = if ($teams.Count -ge 2) { $teams[1] } else { "" }

    Add-Market-Row "ASTRODDS_CONTROL_BOARD_EXISTING" $game $awayTeamName $homeTeamName $pick $price "$price" "internal" ""
}

foreach ($r in $guard) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $price = Get-Val $r @("CurrentEntry","Entry")
    if ($game -eq "" -or $pick -eq "" -or $price -eq "") { continue }

    $teams = $game -split "\s@\s", 2
    $awayTeamName = if ($teams.Count -ge 1) { $teams[0] } else { "" }
    $homeTeamName = if ($teams.Count -ge 2) { $teams[1] } else { "" }

    Add-Market-Row "ASTRODDS_PRICE_GUARD_EXISTING" $game $awayTeamName $homeTeamName $pick $price "$price" "internal" ""
}

# Deduplicate by game/pick/source/book, keep first.
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
Write-Json $rawPayloads $outJson

$apiStatus = if ($apiKey -ne "") { "ODDS_API_KEY_PRESENT" } else { "NO_ODDS_API_KEY_USED_FALLBACK_ONLY" }
$externalRows = @($out | Where-Object { (Get-Val $_ @("Source")) -like "THE_ODDS_API*" }).Count
$internalRows = @($out | Where-Object { (Get-Val $_ @("Source")) -like "ASTRODDS*" }).Count

$lines = @()
$lines += "ASTRODDS 273 FETCH MARKET MONEYLINE SOURCES"
$lines += ""
$lines += "API status: $apiStatus"
$lines += "Market rows total: $($out.Count)"
$lines += "External odds rows: $externalRows"
$lines += "Internal fallback rows: $internalRows"
$lines += ""
$lines += "MARKET SAMPLE"
foreach ($r in ($out | Select-Object -First 12)) {
    $lines += "- $($r.Source) | $($r.Pick) | $($r.Game) | Entry=$($r.Entry) | Book=$($r.Bookmaker)"
}
$lines += ""
$lines += "Output: $outCsv"
$lines += ""
$lines += "IMPORTANT"
$lines += "- For all sportsbook prices, set ODDS_API_KEY first."
$lines += "- Without API key, this uses existing ASTRODDS market rows only."

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
