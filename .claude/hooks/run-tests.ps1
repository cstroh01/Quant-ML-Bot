# Manual full-suite run (no Git). Repo root = two levels above this script.
# Usage: powershell -File .claude\hooks\run-tests.ps1 [-Log <path>]
param([string]$Log = "")
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
if (-not $Log) { $Log = Join-Path $env:TEMP ("quant-ml-bot-pytest-" + (Get-Date -Format "yyyyMMddTHHmmss") + ".txt") }
& $py -m pytest tests -rfEsx 2>&1 | Out-File -Encoding utf8 $Log
$code = $LASTEXITCODE
Write-Output "log: $Log"
Write-Output "exit $code"
exit $code
