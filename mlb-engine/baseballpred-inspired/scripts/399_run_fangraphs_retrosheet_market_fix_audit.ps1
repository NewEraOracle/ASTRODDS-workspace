param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$RunRealDataFetch
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace
$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

function Run-Python($Label, $Name) {
  $path = Join-Path $ScriptDir $Name
  Write-Host "Running $Label..."
  if (!(Test-Path $path)) {
    Write-Host "$Label missing: $path"
    return 1
  }
  $p = Start-Process python -ArgumentList "`"$path`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Write-Host "$Label exit code: $($p.ExitCode)"
  return $p.ExitCode
}

$codes = @()

if ($RunRealDataFetch) {
  $fetch = Join-Path $ScriptDir "397_run_real_baseball_sources_safe.ps1"
  if (Test-Path $fetch) {
    Write-Host "RunRealDataFetch enabled."
    powershell -ExecutionPolicy Bypass -File $fetch -Workspace $Workspace
  }
}

$codes += Run-Python "Source stack audit 396" "396_real_baseball_source_stack_audit.py"
$codes += Run-Python "Fair/model source rewire plan 398" "398_fair_model_source_rewire_plan.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
