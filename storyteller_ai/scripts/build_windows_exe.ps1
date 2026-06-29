param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $ProjectRoot

$python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Virtual environment not found. Run install_dependencies.bat first.'
}

& $python -m pip install --upgrade pip
& $python -m pip install pyinstaller

$distDir = Join-Path $ProjectRoot 'dist'
$buildDir = Join-Path $ProjectRoot 'build'
$exePath = Join-Path $distDir 'StorytellerAI.exe'

# Stop a previously launched packaged app so the exe can be replaced.
Get-Process -Name 'StorytellerAI' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if (Test-Path $exePath) {
    $removed = $false
    for ($i = 0; $i -lt 10; $i++) {
        try {
            Remove-Item $exePath -Force
            $removed = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 300
        }
    }

    if (-not $removed -and (Test-Path $exePath)) {
        throw "Unable to remove locked executable at $exePath. Close StorytellerAI and try again."
    }
}

if (Test-Path $distDir) {
    Remove-Item $distDir -Recurse -Force
}
if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}

& $python -m PyInstaller --noconfirm --clean StorytellerAI.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

Write-Host "Build complete. The exe is in: $distDir\StorytellerAI.exe"
