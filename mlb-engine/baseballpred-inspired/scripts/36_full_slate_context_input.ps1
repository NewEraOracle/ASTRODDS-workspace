$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Base = Resolve-Path "$ScriptDir\.."
$Workspace = Resolve-Path "$Base\..\.."

$FullSlate = Join-Path $Workspace ".astrodds\ASTRODDS-full-slate-strict-latest.json"
$VvsInput = Join-Path $Workspace ".astrodds\VVS-clean-final-latest.json"
$Backup = Join-Path $Workspace ".astrodds\VVS-clean-final-latest.backup-before-full-slate-context.json"
$Report = Join-Path $Base "reports\36_full_slate_context_input_report.txt"

if (-not (Test-Path $FullSlate)) {
  throw "Missing full slate file: $FullSlate"
}

if (Test-Path $VvsInput) {
  Copy-Item $VvsInput $Backup -Force
}

$full = Get-Content $FullSlate -Raw | ConvertFrom-Json

$converted = $full | ForEach-Object {
  [PSCustomObject]@{
    snapshotTime = $_.generatedAt
    gameId = $_.gameId
    date = $_.date
    game = $_.game
    awayTeam = $_.awayTeam
    homeTeam = $_.homeTeam
    pick = $_.pick
    status = $_.status
    marketProbability = $_.marketProbability
    modelProbability = $_.calibratedProbabilityV2
    edgePct = $_.calibratedEdgePct
    modelGapPct = $_.backendModelGapPct
    edgeBucket = $_.calibrationBucket
    confidence = $_.confidence
    risk = $_.risk
    vvsEligible = ($_.strictFullSlateDecision -eq "FULL_SLATE_A_REVIEW")
    vvsReason = $_.strictReason
    strictFullSlateDecision = $_.strictFullSlateDecision
    oppositeSideConflict = $_.oppositeSideConflict
    result = "pending"
    paperOnly = $true
  }
}

$converted | ConvertTo-Json -Depth 10 | Set-Content $VvsInput -Encoding UTF8

Set-Location $Workspace

python ".\mlb-engine\baseballpred-inspired\scripts\08_game_context_snapshot.py"
python ".\mlb-engine\baseballpred-inspired\scripts\09_pitcher_context_snapshot.py"
python ".\mlb-engine\baseballpred-inspired\scripts\10_bullpen_fatigue_snapshot.py"

$game = Get-Content ".\.astrodds\VVS-game-context-latest.json" -Raw | ConvertFrom-Json
$pitcher = Get-Content ".\.astrodds\VVS-pitcher-context-latest.json" -Raw | ConvertFrom-Json
$bullpen = Get-Content ".\.astrodds\VVS-bullpen-context-latest.json" -Raw | ConvertFrom-Json

$lines = @()
$lines += "ASTRODDS 36 FULL SLATE CONTEXT INPUT REPORT"
$lines += "================================================"
$lines += "Status: OK"
$lines += "Full slate rows: $($full.Count)"
$lines += "Converted input rows: $($converted.Count)"
$lines += "Game context rows: $($game.Count)"
$lines += "Pitcher context rows: $($pitcher.Count)"
$lines += "Bullpen context rows: $($bullpen.Count)"
$lines += ""
$lines += "Input: $FullSlate"
$lines += "Output: $VvsInput"
$lines += "Backup: $Backup"
$lines += ""
$lines += "Rule: context only. No real-money automation."

$lines | Set-Content $Report -Encoding UTF8
$lines
