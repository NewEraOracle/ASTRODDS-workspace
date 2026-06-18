param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace
$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

Write-Host "ASTRODDS 397 REAL BASEBALL SOURCES SAFE RUN"
Write-Host "This checks pybaseball and optionally runs existing source acquisition scripts."

$check = Join-Path $ScriptDir "378_check_python_pybaseball_tools.ps1"
$acq = Join-Path $ScriptDir "382_run_real_baseballpred_data_acquisition.ps1"

if (Test-Path $check) {
  Write-Host "Running 378 pybaseball check..."
  powershell -ExecutionPolicy Bypass -File $check
  Write-Host "378 exit code: $LASTEXITCODE"
} else {
  Write-Host "378 check script missing."
}

if (Test-Path $acq) {
  Write-Host "Running 382 real baseball data acquisition..."
  powershell -ExecutionPolicy Bypass -File $acq
  Write-Host "382 exit code: $LASTEXITCODE"
} else {
  Write-Host "382 acquisition script missing."
}

$diag = Join-Path $ScriptDir "396_real_baseball_source_stack_audit.py"
if (Test-Path $diag) {
  Write-Host "Running 396 stack audit after acquisition..."
  python $diag
}
