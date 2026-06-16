param(
  [switch]$NoStartDev
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Base = Resolve-Path "$ScriptDir\.."
$Workspace = Resolve-Path "$Base\..\.."
$Report = Join-Path $Base "reports\31_auto_daily_engine_runner_report.txt"

Set-Location $Workspace

$startedAt = (Get-Date).ToUniversalTime().ToString("o")
$lines = New-Object System.Collections.Generic.List[string]

function Add-Line($text) {
  $lines.Add($text)
  Write-Host $text
}

function Test-Port3000 {
  try {
    return (Test-NetConnection 127.0.0.1 -Port 3000 -InformationLevel Quiet)
  } catch {
    return $false
  }
}

Add-Line "ASTRODDS 31 AUTO DAILY ENGINE RUNNER"
Add-Line "======================================"
Add-Line "Started UTC: $startedAt"
Add-Line ""
Add-Line "Workspace: $Workspace"
Add-Line ""

$serverOk = Test-Port3000

if (-not $serverOk -and -not $NoStartDev) {
  Add-Line "Local server not detected on port 3000."
  Add-Line "Starting npm run dev in a new PowerShell window..."

  Start-Process powershell -WorkingDirectory $Workspace -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$Workspace`"; npm run dev"
  )

  Add-Line "Waiting for localhost:3000..."

  for ($i = 1; $i -le 45; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Port3000) {
      $serverOk = $true
      break
    }
  }
}

if (-not $serverOk) {
  Add-Line "STATUS: FAILED"
  Add-Line "Reason: localhost:3000 is not reachable."
  Add-Line ""
  Add-Line "Fix:"
  Add-Line "Open another PowerShell and run:"
  Add-Line "cd `"$Workspace`""
  Add-Line "npm run dev"
  Add-Line ""
  Add-Line "Then rerun:"
  Add-Line "powershell -ExecutionPolicy Bypass -File `"$ScriptDir\31_auto_daily_engine_runner.ps1`""

  Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
  exit 1
}

Add-Line "Local server: OK"
Add-Line ""

$pipeline = Join-Path $ScriptDir "21_run_engine_v2_full_pipeline.py"

if (-not (Test-Path $pipeline)) {
  Add-Line "STATUS: FAILED"
  Add-Line "Missing pipeline script: $pipeline"
  Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
  exit 1
}

Add-Line "Running credit guard..."
$creditGuard = Join-Path $ScriptDir "48_credit_guard.py"
$creditGuardProcess = Start-Process python -ArgumentList "`"$creditGuard`" record" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
Add-Line "Credit guard exit code: $($creditGuardProcess.ExitCode)"

if ($creditGuardProcess.ExitCode -eq 2) {
  Add-Line "STATUS: CREDIT_GUARD_BLOCKED"
  Add-Line "Engine run skipped to protect odds credits."
  Add-Line ""
  Add-Line "Rule: credit protection only. Paper/manual only. No real-money automation."
  $Lines | Set-Content $Report -Encoding UTF8
  $Lines
  exit 0
}

if ($creditGuardProcess.ExitCode -ne 0) {
  Add-Line "STATUS: CREDIT_GUARD_ERROR"
  Add-Line "Engine run stopped because credit guard returned an error."
  Add-Line ""
  Add-Line "Rule: credit protection only. Paper/manual only. No real-money automation."
  $Lines | Set-Content $Report -Encoding UTF8
  $Lines
  exit 1
}

Add-Line "Running Engine V2 full pipeline..."
Add-Line "Script: $pipeline"
Add-Line ""

$process = Start-Process python -ArgumentList "`"$pipeline`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru

Add-Line ""
Add-Line "Pipeline exit code: $($process.ExitCode)"

if ($process.ExitCode -eq 0) {
  Add-Line "Running full slate context input..."
  $fullSlateContext = Join-Path $ScriptDir "36_full_slate_context_input.ps1"
  $fullSlateProcess = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$fullSlateContext`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Full slate context input exit code: $($fullSlateProcess.ExitCode)"

  Add-Line "Running full slate context final gate..."
  $contextGate = Join-Path $ScriptDir "37_full_slate_context_final_gate.py"
  $contextGateProcess = Start-Process python -ArgumentList "`"$contextGate`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Full slate context gate exit code: $($contextGateProcess.ExitCode)"

  Add-Line "Running threshold context gate..."
  $thresholdGate = Join-Path $Workspace "mlb-engine\scripts\42_threshold_context_gate.py"
  $thresholdGateProcess = Start-Process python -ArgumentList "`"$thresholdGate`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Threshold context gate exit code: $($thresholdGateProcess.ExitCode)"

  Add-Line "Running free injury context gate..."
  $injuryGate = Join-Path $ScriptDir "61_free_injury_context_gate.py"

  if (-not (Test-Path $injuryGate)) {
    Add-Line "STATUS: FAILED"
    Add-Line "Missing free injury context gate: $injuryGate"
    Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
    exit 1
  }

  $injuryGateProcess = Start-Process python -ArgumentList "`"$injuryGate`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Free injury context gate exit code: $($injuryGateProcess.ExitCode)"

  if ($injuryGateProcess.ExitCode -ne 0) {
    Add-Line "SMART_GATE_FAILED_NO_TELEGRAM_SEND"
    Add-Line "Reason: free injury context gate returned non-zero exit code."
    Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
    exit 1
  }
  Add-Line "SMART_GATE_START"

  $smartGateScripts = @(
    "69_official_buy_blocker_audit.py",
    "70_soft_hard_context_gate.py",
    "71_smart_official_buy_promotion.py"
  )

  foreach ($gateScriptName in $smartGateScripts) {
    $gatePath = Join-Path $ScriptDir $gateScriptName

    if (-not (Test-Path $gatePath)) {
      Add-Line "SMART_GATE_FAILED_NO_TELEGRAM_SEND"
      Add-Line "Missing smart gate script: $gatePath"
      Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
      exit 1
    }

    Add-Line "Running smart gate: $gateScriptName"
    $gateProcess = Start-Process python -ArgumentList "`"$gatePath`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "$gateScriptName exit code: $($gateProcess.ExitCode)"

    if ($gateProcess.ExitCode -ne 0) {
      Add-Line "SMART_GATE_FAILED_NO_TELEGRAM_SEND"
      Add-Line "Reason: $gateScriptName returned non-zero exit code."
      Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
      exit 1
    }
  }

  Add-Line "SMART_GATE_APPLIED"

  $engineFinalJson = Join-Path $Workspace ".astrodds\ASTRODDS-engine-final-signals-latest.json"
  $telegramEngineBuyRows = 0

  try {
    if (Test-Path $engineFinalJson) {
      $engineRows = @(Get-Content $engineFinalJson -Raw | ConvertFrom-Json)
      $telegramEngineBuyRows = @(
        $engineRows | Where-Object {
          $_.finalEngineDecision -eq "ENGINE_BUY" -or
          $_.finalDecision -eq "ENGINE_BUY" -or
          $_.decision -eq "ENGINE_BUY"
        }
      ).Count
    }
  } catch {
    Add-Line "telegram_engine_buy_rows=ERROR"
  }

  Add-Line "telegram_engine_buy_rows=$telegramEngineBuyRows"

  Add-Line "Running Telegram final ENGINE_BUY alerts..."
  $finalTelegramAlerts = Join-Path $ScriptDir "30_telegram_final_engine_alerts.py"

  if (-not (Test-Path $finalTelegramAlerts)) {
    Add-Line "SMART_GATE_FAILED_NO_TELEGRAM_SEND"
    Add-Line "Missing Telegram final alerts script: $finalTelegramAlerts"
    Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
    exit 1
  }

  $finalTelegramProcess = Start-Process python -ArgumentList "`"$finalTelegramAlerts`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Telegram final ENGINE_BUY alerts exit code: $($finalTelegramProcess.ExitCode)"

  if ($finalTelegramProcess.ExitCode -ne 0) {
    Add-Line "SMART_GATE_FAILED_NO_TELEGRAM_SEND"
    Add-Line "Reason: Telegram final ENGINE_BUY alert script returned non-zero exit code."
    Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8
    exit 1
  }

  Add-Line "Running Telegram review recap..."
  $reviewRecap = Join-Path $ScriptDir "44_telegram_review_recap.py"
  $reviewRecapProcess = Start-Process python -ArgumentList "`"$reviewRecap`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Telegram review recap exit code: $($reviewRecapProcess.ExitCode)"

  Add-Line "Running daily performance report..."
  $dailyReport = Join-Path $ScriptDir "33_daily_performance_report.py"
  $dailyProcess = Start-Process python -ArgumentList "`"$dailyReport`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Daily performance exit code: $($dailyProcess.ExitCode)"

  Add-Line "Running Telegram daily recap..."
  $recapScript = Join-Path $ScriptDir "34_telegram_daily_recap.ps1"
  $recapProcess = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$recapScript`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Telegram recap exit code: $($recapProcess.ExitCode)"

  Add-Line "Storing odds snapshot..."
  $oddsSnapshotStore = Join-Path $ScriptDir "107_odds_snapshot_store.py"

  if (Test-Path $oddsSnapshotStore) {
    $oddsSnapshotProcess = Start-Process python -ArgumentList "`"$oddsSnapshotStore`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Odds snapshot store exit code: $($oddsSnapshotProcess.ExitCode)"
  } else {
    Add-Line "Odds snapshot store skipped: script not found."
  }
  Add-Line "Running MLB gamePk mapper audit..."
  $gamePkMapper = Join-Path $ScriptDir "109_mlb_gamepk_mapper_audit.py"
  if (Test-Path $gamePkMapper) {
    $gamePkProcess = Start-Process python -ArgumentList "`"$gamePkMapper`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "MLB gamePk mapper exit code: $($gamePkProcess.ExitCode)"
  } else {
    Add-Line "MLB gamePk mapper skipped: script not found."
  }

  Add-Line "Running lineup pitcher live context audit..."
  $lineupPitcherContext = Join-Path $ScriptDir "110_lineup_pitcher_live_context_audit.py"
  if (Test-Path $lineupPitcherContext) {
    $lineupPitcherProcess = Start-Process python -ArgumentList "`"$lineupPitcherContext`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Lineup pitcher live context exit code: $($lineupPitcherProcess.ExitCode)"
  } else {
    Add-Line "Lineup pitcher live context skipped: script not found."
  }
  Add-Line "Running bullpen fatigue context audit..."
  $bullpenContext = Join-Path $ScriptDir "111_bullpen_fatigue_context_audit.py"
  if (Test-Path $bullpenContext) {
    $bullpenProcess = Start-Process python -ArgumentList "`"$bullpenContext`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Bullpen fatigue context exit code: $($bullpenProcess.ExitCode)"
  } else {
    Add-Line "Bullpen fatigue context skipped: script not found."
  }
  Add-Line "Running Over/Under daily audit..."
  $overUnderAudit = Join-Path $ScriptDir "96_over_under_daily_audit.py"

  if (Test-Path $overUnderAudit) {
    $overUnderAuditProcess = Start-Process python -ArgumentList "`"$overUnderAudit`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Over/Under daily audit exit code: $($overUnderAuditProcess.ExitCode)"
  } else {
    Add-Line "Over/Under daily audit skipped: script not found."
  }
  Add-Line "Running weather ballpark context audit..."
  $weatherContextAudit = Join-Path $ScriptDir "108_weather_ballpark_context_audit.py"

  if (Test-Path $weatherContextAudit) {
    $weatherContextProcess = Start-Process python -ArgumentList "`"$weatherContextAudit`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Weather ballpark context audit exit code: $($weatherContextProcess.ExitCode)"
  } else {
    Add-Line "Weather ballpark context audit skipped: script not found."
  }
  Add-Line "Running Over/Under expected total model..."
  $overUnderModel = Join-Path $ScriptDir "98_over_under_expected_total_model.py"

  if (Test-Path $overUnderModel) {
    $overUnderModelProcess = Start-Process python -ArgumentList "`"$overUnderModel`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Over/Under expected total model exit code: $($overUnderModelProcess.ExitCode)"
  } else {
    Add-Line "Over/Under expected total model skipped: script not found."
  }
  Add-Line "Running Over/Under probability edge model..."
  $overUnderProbabilityEdge = Join-Path $ScriptDir "100_over_under_probability_edge_model.py"

  if (Test-Path $overUnderProbabilityEdge) {
    $overUnderProbabilityEdgeProcess = Start-Process python -ArgumentList "`"$overUnderProbabilityEdge`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Over/Under probability edge model exit code: $($overUnderProbabilityEdgeProcess.ExitCode)"
  } else {
    Add-Line "Over/Under probability edge model skipped: script not found."
  }
  Add-Line "Running O/U A+ Telegram sender..."
$ouAPlusTelegram = Join-Path $ScriptDir "136_send_ou_aplus_telegram.py"
if (Test-Path $ouAPlusTelegram) {
  $ouAPlusProcess = Start-Process python -ArgumentList "`"$ouAPlusTelegram`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "O/U A+ Telegram exit code: $($ouAPlusProcess.ExitCode)"
} else {
  Add-Line "O/U A+ Telegram skipped: script not found."
}
Add-Line "Running public board categories..."
  $publicBoard = Join-Path $ScriptDir "94_public_board_categories.py"

  if (Test-Path $publicBoard) {
    $publicBoardProcess = Start-Process python -ArgumentList "`"$publicBoard`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Public board categories exit code: $($publicBoardProcess.ExitCode)"
  } else {
    Add-Line "Public board categories skipped: script not found."
  }

  Add-Line "Running Moneyline A/A+ Telegram sender..."
  $moneylineAPickTelegram = Join-Path $ScriptDir "135_send_moneyline_a_aplus_telegram.py"
  if (Test-Path $moneylineAPickTelegram) {
    $moneylineAPickProcess = Start-Process python -ArgumentList "`"$moneylineAPickTelegram`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Moneyline A/A+ Telegram exit code: $($moneylineAPickProcess.ExitCode)"
  } else {
    Add-Line "Moneyline A/A+ Telegram skipped: script not found."
  }
  Add-Line "Syncing clean Moneyline picks into CSV..."
  $cleanCsvSync = Join-Path $ScriptDir "134_sync_clean_moneyline_picks_csv.py"
  if (Test-Path $cleanCsvSync) {
    $cleanCsvSyncProcess = Start-Process python -ArgumentList "`"$cleanCsvSync`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Clean Moneyline CSV sync exit code: $($cleanCsvSyncProcess.ExitCode)"
  } else {
    Add-Line "Clean Moneyline CSV sync skipped: script not found."
  }
  Add-Line "Running Telegram result tracking..."
  $resultTracking = Join-Path $ScriptDir "81_telegram_result_tracking.py"

  if (Test-Path $resultTracking) {
    $resultTrackingProcess = Start-Process python -ArgumentList "`"$resultTracking`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
    Add-Line "Telegram result tracking exit code: $($resultTrackingProcess.ExitCode)"
  } else {
    Add-Line "Telegram result tracking skipped: script not found."
  }
  Add-Line "STATUS: OK"
  Add-Line "Engine run complete."
  Add-Line ""
  Add-Line "Outputs updated:"
  Add-Line "- .astrodds/ASTRODDS-engine-final-signals-latest.json"
  Add-Line "- .astrodds/ASTRODDS-engine-signal-ledger.json"
  Add-Line "- .astrodds/ASTRODDS-odds-snapshot-ledger.json"
  Add-Line "- public/astrodds-proof-log.html"
  Add-Line "- public/astrodds-proof-log.json"
  Add-Line ""
  Add-Line "Telegram:"
  Add-Line "- Sends only ENGINE_BUY A+/A."
  Add-Line "- Duplicate protection prevents spam."
} else {
  Add-Line "STATUS: FAILED"
  Add-Line "Engine pipeline returned a non-zero exit code."
}

Add-Line ""
Add-Line "Finished UTC: $((Get-Date).ToUniversalTime().ToString("o"))"
Add-Line "Report: $Report"
Add-Line ""
Add-Line "Rule: Paper/manual only. No real-money automation."

Set-Content -Path $Report -Value ($lines -join "`n") -Encoding UTF8

if ($process.ExitCode -ne 0) {
  exit $process.ExitCode
}




















