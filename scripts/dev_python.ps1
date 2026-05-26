param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PythonArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$venvConfig = Join-Path $root ".venv\pyvenv.cfg"

if (Test-Path $venvPython) {
  & $venvPython @PythonArgs
  if ($LASTEXITCODE -eq 0) {
    exit 0
  }
  Write-Warning ".venv Python failed with exit code $LASTEXITCODE; trying global Python."
}

if (Test-Path $venvConfig) {
  $baseExecutable = Select-String -LiteralPath $venvConfig -Pattern "^executable\s*=\s*(.+)$" | Select-Object -First 1
  if ($baseExecutable -and (Test-Path $baseExecutable.Matches[0].Groups[1].Value.Trim())) {
    $basePython = $baseExecutable.Matches[0].Groups[1].Value.Trim()
    Write-Warning ".venv launcher appears broken; using base interpreter from pyvenv.cfg: $basePython"
    & $basePython @PythonArgs
    exit $LASTEXITCODE
  }
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  & $py.Source -3 @PythonArgs
  exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & $python.Source @PythonArgs
  exit $LASTEXITCODE
}

Write-Error "No Python runtime found. Install Python 3.11+ or create .venv."
exit 1
