$ErrorActionPreference = "Continue"
function Read-JsonSafe($path) { if (!(Test-Path $path)) { return $null }; try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null } }
function JVal($obj, $name, $default="0") { if ($null -eq $obj) { return $default }; try { $p=$obj.PSObject.Properties[$name]; if($null -ne $p -and "$($p.Value)".Trim() -ne ""){ return "$($p.Value)" } } catch {}; return $default }
$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$outTxt = Join-Path $astro "ASTRODDS-383-real-premium-source-acquisition-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-383-real-premium-source-acquisition-report-latest.json"
$x = Read-JsonSafe (Join-Path $astro "ASTRODDS-379-fetch-true-xfip-fangraphs-pybaseball-latest.json")
$p = Read-JsonSafe (Join-Path $astro "ASTRODDS-380-fetch-team-platoon-statcast-pybaseball-latest.json")
$l = Read-JsonSafe (Join-Path $astro "ASTRODDS-381-fetch-true-leverage-fangraphs-pybaseball-latest.json")
$premium = Read-JsonSafe (Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.json")
$milestone = Read-JsonSafe (Join-Path $astro "ASTRODDS-374-settled-results-milestone-promoter-latest.json")
$status = "REAL_DATA_ACQUISITION_READY"
$warnings = @()
if (([int](JVal $x "rows")) -eq 0) { $warnings += "true xFIP fetch has 0 rows or failed" }
if (([int](JVal $p "rows")) -eq 0) { $warnings += "platoon Statcast fetch has 0 rows or failed" }
if (([int](JVal $l "rows")) -eq 0) { $warnings += "true leverage fetch has 0 rows or columns unavailable" }
$lines = @()
$lines += "ASTRODDS 383 REAL PREMIUM SOURCE ACQUISITION REPORT"
$lines += ""
$lines += "Status: $status"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "SOURCE ROWS"
$lines += "- True xFIP rows: $(JVal $x 'rows') | status=$(JVal $x 'status' 'UNKNOWN')"
$lines += "- Platoon rows: $(JVal $p 'rows') | status=$(JVal $p 'status' 'UNKNOWN')"
$lines += "- True leverage rows: $(JVal $l 'rows') | status=$(JVal $l 'status' 'UNKNOWN')"
$lines += ""
$lines += "PREMIUM CONNECTED"
$lines += "- Home plate umpire connected rows: $(JVal $premium 'homePlateUmpireConnectedRows')"
$lines += "- Real bullpen pitch usage teams: $(JVal $premium 'realBullpenPitchUsageTeams')"
$lines += "- Platoon fully connected rows: $(JVal $premium 'platoonFullyConnectedRows')"
$lines += "- True xFIP fully connected rows: $(JVal $premium 'trueXfipFullyConnectedRows')"
$lines += "- True leverage connected teams: $(JVal $premium 'trueLeverageConnectedTeams')"
$lines += ""
$lines += "MILESTONES"
$lines += "- Settled labeled rows: $(JVal $milestone 'settledLabeledRows')"
$lines += "- Mode: $(JVal $milestone 'mode' 'SOURCE_FIRST_ONLY')"
$lines += ""
$lines += "WARNINGS"
if ($warnings.Count -eq 0) { $lines += "- none" } else { foreach ($w in $warnings) { $lines += "- $w" } }
$lines += ""
$lines += "NO-FAKE RULE"
$lines += "- xFIP uses FanGraphs/pybaseball if available."
$lines += "- Platoon uses real Statcast events; wRC+ stays blank unless a real export provides it."
$lines += "- True leverage uses FanGraphs leverage columns only if exposed."
[pscustomobject]@{generatedAt=(Get-Date).ToString("o");status=$status;warnings=@($warnings);trueXfipRows=JVal $x "rows";platoonRows=JVal $p "rows";trueLeverageRows=JVal $l "rows";premium=$premium;milestone=$milestone} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
