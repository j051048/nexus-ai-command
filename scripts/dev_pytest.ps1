param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $root "nexus_backend"

Push-Location (Join-Path $root "nexus_backend")
try {
  & (Join-Path $PSScriptRoot "dev_python.ps1") -m pytest @PytestArgs
} finally {
  Pop-Location
}
exit $LASTEXITCODE
