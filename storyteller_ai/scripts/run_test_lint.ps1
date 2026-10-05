$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $repoRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$previousLocation = Get-Location
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = (@($repoRoot, $workspaceRoot, $previousPythonPath) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
$exitCode = 1
Set-Location $repoRoot

try {
    & $pythonExe -m pytest -q
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        & $pythonExe -m ruff check backend tests
        $exitCode = $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Set-Location $previousLocation
}

exit $exitCode
