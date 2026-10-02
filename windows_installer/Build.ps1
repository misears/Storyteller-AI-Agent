param(
    [string]$ProjectRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'storyteller_ai'),
    [string]$PythonVersion = '3.12.10',
    [string]$CompilerPath,
    [switch]$PrepareOnly
)

. (Join-Path $PSScriptRoot 'Setup.Common.ps1')
& (Join-Path $PSScriptRoot 'Test-Installer.ps1')
if ($PythonVersion -notmatch '^3\.12\.\d+$') { throw 'This installer currently targets CPython 3.12 x64 wheels.' }

$output = Join-Path $PSScriptRoot 'output'
$bundle = Join-Path $output 'StorytellerAI-Install'
$payload = Join-Path $bundle 'payload'
$application = Join-Path $payload 'app'
$wheels = Join-Path $payload 'wheels'
if (Test-Path $bundle) { Remove-Item $bundle -Recurse -Force }
$null = New-Item $application, $wheels -ItemType Directory -Force
foreach ($script in @('Install.ps1', 'Launch.ps1', 'Setup.Common.ps1', 'Install.cmd', 'README.md')) {
    Copy-Item (Join-Path $PSScriptRoot $script) $bundle
}
foreach ($folder in @('backend', 'frontend')) {
    $source = Join-Path $ProjectRoot $folder
    foreach ($file in Get-ChildItem $source -File -Recurse) {
        $relative = $file.FullName.Substring($ProjectRoot.TrimEnd('\').Length + 1)
        if ($relative -match '(^|\\)(__pycache__|data)(\\|$)' -or $file.Extension -eq '.pyc') { continue }
        $destination = Join-Path $application $relative
        $null = New-Item (Split-Path -Parent $destination) -ItemType Directory -Force
        Copy-Item $file.FullName $destination
    }
}
Copy-Item (Join-Path $ProjectRoot 'desktop_entry.py') $application
Copy-Item (Join-Path $ProjectRoot 'requirements.txt') $payload

$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = (Get-Command python.exe -ErrorAction Stop).Source }
Write-Host 'Resolving the exact application dependencies for Python 3.12 on Windows x64...'
Invoke-CheckedProcess $python @('-m', 'pip', 'download', '--only-binary=:all:', '--platform', 'win_amd64', '--python-version', '312', '--implementation', 'cp', '--abi', 'cp312', '--dest', $wheels, '-r', (Join-Path $payload 'requirements.txt'))

Write-Host 'Downloading and verifying the official Python installer...'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$pythonInstaller = Join-Path $payload 'python-installer.exe'
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" -OutFile $pythonInstaller -UseBasicParsing
if ((Get-AuthenticodeSignature $pythonInstaller).Status -ne 'Valid') { throw 'The Python installer signature is not valid.' }
$manifest = @(Get-ChildItem $payload -File -Recurse | ForEach-Object {
    @{ path = $_.FullName.Substring($payload.Length + 1); sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
})
ConvertTo-Json -InputObject $manifest -Depth 3 | Set-Content (Join-Path $payload 'SHA256.json') -Encoding UTF8
Assert-PayloadIntegrity $payload
Compress-Archive -Path $bundle -DestinationPath (Join-Path $output 'StorytellerAI-Install.zip') -Force
Write-Host "Installable ZIP created: $output\StorytellerAI-Install.zip"
if ($PrepareOnly) { return }

if (-not $CompilerPath) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $CompilerPath = $command.Source }
    else {
        foreach ($candidate in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
            if (Test-Path $candidate) { $CompilerPath = $candidate; break }
        }
    }
}
if (-not $CompilerPath -or -not (Test-Path $CompilerPath)) {
    $tools = Join-Path $output 'tools'
    $compilerRoot = Join-Path $tools 'InnoSetup'
    $CompilerPath = Join-Path $compilerRoot 'ISCC.exe'
    if (-not (Test-Path $CompilerPath)) {
        $null = New-Item $tools -ItemType Directory -Force
        $download = Join-Path $tools 'innosetup-6.7.3.exe'
        Write-Host 'Downloading the signed Inno Setup compiler in portable mode (no system-wide installation)...'
        Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $download -UseBasicParsing
        if ((Get-AuthenticodeSignature $download).Status -ne 'Valid') { throw 'The compiler installer signature is not valid.' }
        $process = Start-Process $download -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', '/PORTABLE=1', '/NOICONS', "/DIR=`"$compilerRoot`"") -Wait -PassThru
        if ($process.ExitCode -ne 0 -or -not (Test-Path $CompilerPath)) { throw 'Portable compiler setup failed. Supply an installed compiler with -CompilerPath.' }
    }
}
Invoke-CheckedProcess $CompilerPath @((Join-Path $PSScriptRoot 'StorytellerAI.iss'))
Write-Host "Windows setup executable created: $output\StorytellerAI-Setup.exe"