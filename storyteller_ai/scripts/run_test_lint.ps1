$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

& $pythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $pythonExe -m ruff check backend tests
exit $LASTEXITCODE
