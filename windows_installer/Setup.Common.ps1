Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-CheckedProcess {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed (exit $LASTEXITCODE). See the setup log for details."
    }
}

function Get-RecommendedModel {
    param([double]$MemoryGB, [double]$VideoMemoryGB)
    if ($MemoryGB -ge 16 -and $VideoMemoryGB -ge 8) { return 'qwen3:8b' }
    if ($MemoryGB -ge 8) { return 'qwen3:4b' }
    return 'qwen3:1.7b'
}

function Find-Ollama {
    $installed = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $installed) { return $installed }
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Find-Python312 {
    foreach ($key in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath', 'HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
        if (-not (Test-Path $key)) { continue }
        $folder = (Get-Item $key).GetValue('')
        if (-not $folder) { continue }
        $candidate = Join-Path $folder 'python.exe'
        if (Test-Path $candidate) {
            $result = & $candidate -I -c 'import sys; print(sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $result -eq 'True') { return $candidate }
        }
    }
    return $null
}

function Test-OllamaReady {
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3
        return $true
    }
    catch { return $false }
}

function Wait-OllamaReady {
    param([int]$TimeoutSeconds = 60)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (Test-OllamaReady) { return }
        [System.Threading.Tasks.Task]::Delay(500).GetAwaiter().GetResult()
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'The AI service did not start. Restart Windows and run Repair Storyteller AI from the Start menu.'
}

function Assert-PayloadIntegrity {
    param([string]$PayloadRoot)
    $manifest = Join-Path $PayloadRoot 'SHA256.json'
    if (-not (Test-Path $manifest)) { throw 'The installer checksum manifest is missing. Rebuild the installer.' }
    $entries = Get-Content $manifest -Raw | ConvertFrom-Json
    foreach ($entry in $entries) {
        $root = [IO.Path]::GetFullPath($PayloadRoot).TrimEnd('\') + '\'
        $target = [IO.Path]::GetFullPath((Join-Path $PayloadRoot $entry.path))
        if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The installer manifest contains an invalid path.'
        }
        if (-not (Test-Path $target) -or (Get-FileHash $target -Algorithm SHA256).Hash -ne $entry.sha256) {
            throw "An installer file is missing or damaged: $($entry.path). Download the installer again."
        }
    }
}

function Get-PreflightReport {
    param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\StorytellerAI'))
    $system = Get-CimInstance Win32_ComputerSystem
    $memory = [Math]::Round($system.TotalPhysicalMemory / 1GB)
    $cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
    $graphics = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '
    $videoMemory = 0
    $nvidia = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($nvidia) {
        $values = & $nvidia.Source --query-gpu=memory.total --format=csv,noheader,nounits
        if ($LASTEXITCODE -eq 0) {
            foreach ($value in $values) {
                $parsed = 0.0
                if ([double]::TryParse($value.Trim(), [ref]$parsed)) {
                    $videoMemory = [Math]::Max($videoMemory, $parsed / 1024)
                }
            }
        }
    }
    $ollama = Find-Ollama
    $python = Test-Path (Join-Path $InstallRoot 'runtime\python.exe')
    $existingPython = Find-Python312
    $environmentPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
    $packagesReady = $false
    if (Test-Path $environmentPython) {
        $null = & $environmentPython -m pip check 2>$null
        $packagesReady = $LASTEXITCODE -eq 0
    }
    $ocr = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    $ocrPath = Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
    @(
        "Processor: $cpu"
        "System memory: $memory GB"
        "Graphics: $graphics"
        "Recommended model: $(Get-RecommendedModel $memory $videoMemory)"
        ''
        $(if ($python) { 'Python: the private runtime is already installed.' } elseif ($existingPython) { 'Python: compatible 3.12 x64 installation found; it will be reused without changing it.' } else { 'Python: compatible runtime missing; a private runtime will be installed automatically.' })
        $(if (Test-Path $environmentPython) { 'Virtual environment: found; it will be checked and repaired.' } else { 'Virtual environment: missing; it will be created automatically.' })
        $(if ($packagesReady) { 'Python packages: no installed dependency conflicts detected; bundled versions will be verified.' } else { 'Python packages: missing or need checking; bundled packages will be installed automatically.' })
        $(if ($ollama) { 'Ollama: found; the existing installation will be reused.' } else { 'Ollama: missing; the included official installer will install it for your account.' })
        'AI model: a missing selected model will be downloaded (roughly 2-6 GB).'
        $(if ($ocr -or (Test-Path $ocrPath)) { 'Optional scanned-PDF reader (Tesseract): found.' } else { 'Optional scanned-PDF reader (Tesseract): missing. Normal text PDFs work; scanned PDFs need separate OCR installation.' })
        ''
        'Allow at least 20 GB free space on both the installation and Windows profile drives.'
        'Internet is needed for the first model download unless the model is already installed.'
        'No GPU is required. Small models work on CPU, but responses will be slower.'
        'Other software installers may display their own prompts. No Python knowledge is needed.'
    ) -join [Environment]::NewLine
}