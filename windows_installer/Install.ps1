param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\StorytellerAI'),
    [ValidateSet('qwen3:8b', 'qwen3:4b', 'qwen3:1.7b')][string]$Model = 'qwen3:4b',
    [switch]$CheckOnly,
    [string]$ReportPath,
    [switch]$SkipConfirmation,
    [switch]$InstallOCR
)

. (Join-Path $PSScriptRoot 'Setup.Common.ps1')

if ($CheckOnly) {
    $report = Get-PreflightReport $InstallRoot
    if ($ReportPath) { Set-Content $ReportPath $report -Encoding UTF8 }
    else { Write-Host $report }
    exit 0
}

$logRoot = Join-Path $env:LOCALAPPDATA 'StorytellerAI\logs'
$null = New-Item $logRoot -ItemType Directory -Force
$log = Join-Path $logRoot ('setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
Start-Transcript -Path $log | Out-Null
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'This installer requires 64-bit Windows on an Intel or AMD processor.'
    }
    Write-Host 'Storyteller AI - installation and repair' -ForegroundColor Cyan
    Write-Host (Get-PreflightReport $InstallRoot)
    Write-Host "Selected model: $Model"
    if (-not $SkipConfirmation) {
        $answer = Read-Host 'Continue with software installation and model download? Type YES to continue'
        if ($answer -ne 'YES') { throw 'Installation cancelled. No application software was installed.' }
    }
    if (-not $SkipConfirmation -and -not $InstallOCR) {
        $ocrAnswer = Read-Host 'Optional: install scanned-PDF OCR using WinGet? Windows may request approval. Type YES to install, or press Enter to skip'
        $InstallOCR = $ocrAnswer -ceq 'YES'
    }
    foreach ($root in @([IO.Path]::GetPathRoot($InstallRoot), [IO.Path]::GetPathRoot($env:USERPROFILE)) | Select-Object -Unique) {
        $drive = Get-PSDrive -Name $root.TrimEnd('\').TrimEnd(':')
        if ($drive.Free -lt 20GB) { throw "Not enough space on $root. Free at least 20 GB and try again." }
    }
    $payload = Join-Path $PSScriptRoot 'payload'
    Assert-PayloadIntegrity $payload
    $null = New-Item $InstallRoot -ItemType Directory -Force
    $runtime = Join-Path $InstallRoot 'runtime'
    $python = Join-Path $runtime 'python.exe'
    if (-not (Test-Path $python)) {
        $existingPython = Find-Python312
        if ($existingPython) { $python = $existingPython }
    }
    if (-not (Test-Path $python)) {
        Write-Host '[1/6] Installing a private Python runtime...'
        $python = Install-PrivatePython (Join-Path $payload 'python-runtime.zip') $runtime
    }
    if (-not (Test-Path $python)) { throw 'Python installation did not create the expected runtime. Run setup again.' }
    Write-Host '[2/6] Creating and checking the private virtual environment...'
    $environment = Join-Path $InstallRoot '.venv'
    $environmentPython = Join-Path $environment 'Scripts\python.exe'
    Invoke-CheckedProcess $python @('-m', 'venv', $environment)
    Invoke-CheckedProcess $environmentPython @('-m', 'pip', 'install', '--no-index', '--find-links', (Join-Path $payload 'wheels'), '-r', (Join-Path $payload 'requirements.txt'))
    Invoke-CheckedProcess $environmentPython @('-m', 'pip', 'check')
    Write-Host '[3/6] Installing the application...'
    $application = Join-Path $InstallRoot 'app'
    $null = New-Item $application -ItemType Directory -Force
    Copy-Item (Join-Path $payload 'app\*') $application -Recurse -Force
    foreach ($script in @('Launch.ps1', 'Install.ps1', 'Install-OCR.ps1', 'Setup.Common.ps1')) {
        if ([IO.Path]::GetFullPath($PSScriptRoot) -ne [IO.Path]::GetFullPath($InstallRoot)) {
            Copy-Item (Join-Path $PSScriptRoot $script) $InstallRoot -Force
        }
    }
    if ([IO.Path]::GetFullPath($PSScriptRoot) -ne [IO.Path]::GetFullPath($InstallRoot)) {
        Copy-Item $payload $InstallRoot -Recurse -Force
    }
    $data = Join-Path $env:LOCALAPPDATA 'StorytellerAI\data'
    $null = New-Item $data -ItemType Directory -Force
    @("LLM_PROVIDER=ollama", 'OLLAMA_URL=http://127.0.0.1:11434', "OLLAMA_MODEL=$Model", "LLM_MODEL=$Model") | Set-Content (Join-Path $application '.env') -Encoding ASCII
    Write-Host '[4/6] Checking the local AI software...'
    $ollama = Find-Ollama
    if (-not $ollama) {
        Write-Host 'Downloading Ollama from its official website. This can be a large download.'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $download = Join-Path $logRoot 'OllamaSetup.exe'
        Invoke-WebRequest 'https://ollama.com/download/OllamaSetup.exe' -OutFile $download -UseBasicParsing
        if ((Get-AuthenticodeSignature $download).Status -ne 'Valid') {
            throw 'The Ollama installer signature could not be verified. Setup stopped for your safety.'
        }
        Write-Host 'Download verified. Installing Ollama; its desktop app may open automatically...'
        $installerExitCode = Invoke-InstallerProcess $download @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-')
        if ($installerExitCode -notin @(0, 3010)) { throw "Ollama installation failed (exit $installerExitCode)." }
        $ollama = Find-Ollama
        if (-not $ollama) { throw 'Ollama was not found after installation. Restart Windows and run Repair Storyteller AI.' }
        Remove-Item $download -Force
    }
    if (-not (Test-OllamaReady)) { $null = Start-Process $ollama -ArgumentList 'serve' -WindowStyle Hidden -PassThru }
    Wait-OllamaReady
    Write-Host "[5/6] Checking and downloading $Model. Keep this window open..."
    $models = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
    if ($Model -notin @($models.models | ForEach-Object { $_.name })) {
        Invoke-CheckedProcess $ollama @('pull', $Model)
    }
    $models = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
    if ($Model -notin @($models.models | ForEach-Object { $_.name })) { throw 'The model download could not be verified. Run repair to retry.' }
    Write-Host '[6/6] Testing the AI model and creating shortcuts...'
    $request = @{ model = $Model; prompt = 'Reply with OK.'; stream = $false; think = $false; options = @{ num_predict = 8; num_ctx = 4096 } } | ConvertTo-Json -Depth 4
    $response = Invoke-RestMethod 'http://127.0.0.1:11434/api/generate' -Method Post -ContentType 'application/json' -Body $request -TimeoutSec 300
    if (-not $response.response) { throw 'The AI model loaded but did not produce text. Run repair or select a smaller model.' }
    $env:STORYTELLER_DATA_DIR = $data
    Push-Location $application
    try { Invoke-CheckedProcess $environmentPython @('-c', 'from backend.main import app; assert app.title') }
    finally { Pop-Location }
    $shell = New-Object -ComObject WScript.Shell
    $startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Storyteller AI'
    $null = New-Item $startMenu -ItemType Directory -Force
    foreach ($location in @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Storyteller AI.lnk'), (Join-Path $startMenu 'Storyteller AI.lnk'), (Join-Path $startMenu 'Repair Storyteller AI.lnk'))) {
        $shortcut = $shell.CreateShortcut($location)
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $script = if ($location.EndsWith('Repair Storyteller AI.lnk')) { 'Install.ps1' } else { 'Launch.ps1' }
        $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $InstallRoot $script)`"" + $(if ($script -eq 'Install.ps1') { " -InstallRoot `"$InstallRoot`" -Model $Model" } else { '' })
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Save()
    }
    $ocrShortcut = $shell.CreateShortcut((Join-Path $startMenu 'Repair OCR for Storyteller AI.lnk'))
    $ocrShortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $ocrShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $InstallRoot 'Install-OCR.ps1')`" -Interactive"
    $ocrShortcut.WorkingDirectory = $InstallRoot
    $ocrShortcut.Save()
    if ($InstallOCR) {
        Write-Host '[Optional] Setting up scanned-PDF OCR...'
        try {
            Invoke-CheckedProcess (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $InstallRoot 'Install-OCR.ps1'), '-Consent')
        }
        catch {
            Write-Host "OCR setup was not completed: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host 'Storyteller AI is installed and text-based PDFs still work. Select Repair OCR for Storyteller AI from the Start menu to retry.' -ForegroundColor Yellow
        }
    }
    Write-Host 'Installation complete. Open Storyteller AI from your desktop.' -ForegroundColor Green
}
catch {
    Write-Host "Setup could not finish: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log: $log"
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null