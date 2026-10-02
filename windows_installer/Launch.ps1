. (Join-Path $PSScriptRoot 'Setup.Common.ps1')

$logs = Join-Path $env:LOCALAPPDATA 'StorytellerAI\logs'
$null = New-Item $logs -ItemType Directory -Force
Start-Transcript -Path (Join-Path $logs 'launch.log') -Append | Out-Null
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw 'The private Python environment is missing. Run Repair Storyteller AI from the Start menu.' }
    $ollama = Find-Ollama
    if (-not $ollama) { throw 'The AI software is missing. Run Repair Storyteller AI from the Start menu.' }
    if (-not (Test-OllamaReady)) { $null = Start-Process $ollama -ArgumentList 'serve' -WindowStyle Hidden -PassThru }
    Wait-OllamaReady
    $env:STORYTELLER_DATA_DIR = Join-Path $env:LOCALAPPDATA 'StorytellerAI\data'
    $ocr = Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
    if (Test-Path $ocr) { $env:TESSERACT_CMD = $ocr }
    $env:STORYTELLER_HOST = '127.0.0.1'
    $listener = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($listener) {
        throw 'Port 8000 is already in use. Close any running Storyteller window or the other program using that port, then try again.'
    }
    $env:STORYTELLER_PORT = '8000'
    Write-Host 'Storyteller AI is starting. Your browser will open automatically.'
    Write-Host 'Keep this window open while playing. Close it to stop Storyteller AI.'
    Push-Location (Join-Path $PSScriptRoot 'app')
    try { Invoke-CheckedProcess $python @('desktop_entry.py') }
    finally { Pop-Location }
}
catch {
    Write-Host "Storyteller AI could not start: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Logs: $logs"
    $null = Read-Host 'Press Enter to close'
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null