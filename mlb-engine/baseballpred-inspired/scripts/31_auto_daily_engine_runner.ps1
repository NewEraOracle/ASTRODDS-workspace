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

  Add-Line "Running daily performance report..."
  $dailyReport = Join-Path $ScriptDir "33_daily_performance_report.py"
  $dailyProcess = Start-Process python -ArgumentList "`"$dailyReport`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Daily performance exit code: $($dailyProcess.ExitCode)"

  Add-Line "Running Telegram daily recap..."
  $recapScript = Join-Path $ScriptDir "34_telegram_daily_recap.ps1"
  $recapProcess = Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$recapScript`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Add-Line "Telegram recap exit code: $($recapProcess.ExitCode)"

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


