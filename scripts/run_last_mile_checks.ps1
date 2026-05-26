param(
  [switch]$RealBackend,
  [switch]$RealMigrations
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root

try {
  & .\scripts\dev_python.ps1 .\scripts\scan_rls_coverage.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & .\scripts\dev_python.ps1 .\scripts\scan_rls_policy_columns.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & .\scripts\dev_python.ps1 .\scripts\scan_migration_schema_conflicts.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & .\scripts\dev_python.ps1 .\scripts\audit_schema_convergence.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  if ($RealMigrations) {
    & .\scripts\dev_python.ps1 .\scripts\verify_migration_replay.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }

  $env:PYTHONPATH = Join-Path $root "nexus_backend"
  & .\scripts\dev_pytest.ps1 nexus_backend\tests\production_proof -q -o addopts=''
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  if ($RealBackend) {
    $env:RUN_REAL_PRODUCTION_PROOF = "1"
    & .\scripts\dev_pytest.ps1 nexus_backend\tests\integration -q -o addopts=''
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
} finally {
  Pop-Location
}
