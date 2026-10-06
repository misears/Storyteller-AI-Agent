param([string]$RuntimeArchivePath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Setup.Common.ps1')

function Assert-Equal {
    param($Actual, $Expected)
    if ($Actual -ne $Expected) { throw "Expected '$Expected', got '$Actual'." }
}

$script:installerWaited = $false
function Start-Process {
    param([string]$FilePath, [string[]]$ArgumentList, [switch]$PassThru, [switch]$Wait)
    Assert-Equal $FilePath 'test-installer.exe'
    Assert-Equal ($ArgumentList -join ' ') '/VERYSILENT /NORESTART'
    Assert-Equal $PassThru.IsPresent $true
    Assert-Equal $Wait.IsPresent $false
    $process = [pscustomobject]@{ Handle = 1; ExitCode = 3010 }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { $script:installerWaited = $true }
    return $process
}
try {
    Assert-Equal (Invoke-InstallerProcess 'test-installer.exe' @('/VERYSILENT', '/NORESTART')) 3010
    Assert-Equal $script:installerWaited $true
}
finally { Remove-Item Function:\Start-Process }

foreach ($file in Get-ChildItem $PSScriptRoot -Filter '*.ps1') {
    $tokens = $null
    $parseErrors = $null
    $syntaxTree = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
    if ($file.Name -eq 'Launch.ps1') {
        $browserSetting = @($syntaxTree.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
            $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
            $node.Left.VariablePath.UserPath -eq 'env:STORYTELLER_OPEN_BROWSER'
        }, $true))
        Assert-Equal $browserSetting.Count 1
        $browserValue = @($browserSetting[0].Right.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.StringConstantExpressionAst]
        }, $true))
        Assert-Equal $browserValue.Count 1
        Assert-Equal $browserValue[0].Value '1'
        $browserLink = @($syntaxTree.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.CommandAst] -and
            $node.GetCommandName() -eq 'Write-Host' -and
            $node.Extent.Text -like '*Browser link: http://*'
        }, $true))
        Assert-Equal $browserLink.Count 1
        $originalHost = $env:STORYTELLER_HOST
        $originalPort = $env:STORYTELLER_PORT
        try {
            $env:STORYTELLER_HOST = '127.0.0.1'
            $env:STORYTELLER_PORT = '8000'
            $output = (& ([scriptblock]::Create($browserLink[0].Extent.Text)) 6>&1 | Out-String).Trim()
            Assert-Equal $output 'Browser link: http://127.0.0.1:8000/'
            $env:STORYTELLER_PORT = '8123'
            $output = (& ([scriptblock]::Create($browserLink[0].Extent.Text)) 6>&1 | Out-String).Trim()
            Assert-Equal $output 'Browser link: http://127.0.0.1:8123/'
        }
        finally {
            $env:STORYTELLER_HOST = $originalHost
            $env:STORYTELLER_PORT = $originalPort
        }
    }
}

$installerDefinition = Get-Content (Join-Path $PSScriptRoot 'StorytellerAI.iss') -Raw
$uninstallEntries = [regex]::Match($installerDefinition, '(?ms)^\[UninstallDelete\]\r?\n(.*?)(?=^\[|\z)').Groups[1].Value
$allowedUninstallEntries = @(
    'Type: filesandordirs; Name: "{app}\app"'
    'Type: filesandordirs; Name: "{app}\.venv"'
    'Type: filesandordirs; Name: "{app}\runtime"'
    'Type: files; Name: "{userdesktop}\Storyteller AI.lnk"'
    'Type: files; Name: "{userprograms}\Storyteller AI\Storyteller AI.lnk"'
    'Type: files; Name: "{userprograms}\Storyteller AI\Repair Storyteller AI.lnk"'
    'Type: files; Name: "{userprograms}\Storyteller AI\Repair OCR for Storyteller AI.lnk"'
    'Type: dirifempty; Name: "{userprograms}\Storyteller AI"'
)
$actualUninstallEntries = @($uninstallEntries -split '\r?\n' | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() })
Assert-Equal $actualUninstallEntries.Count $allowedUninstallEntries.Count
foreach ($entry in $actualUninstallEntries) {
    Assert-Equal ($entry -cin $allowedUninstallEntries) $true
}
Assert-Equal ($installerDefinition -match '(?m)^\[UninstallRun\]') $false
Assert-Equal ($installerDefinition.Contains('Name: "{group}\Uninstall Storyteller AI"; Filename: "{uninstallexe}"')) $true

Assert-Equal (Get-RecommendedModel 64 8) 'qwen3:8b'
Assert-Equal (Get-RecommendedModel 16 0) 'qwen3:4b'
Assert-Equal (Get-RecommendedModel 4 0) 'qwen3:1.7b'
Assert-Equal (Test-TesseractLanguageOutput @('List of available languages:', 'eng', 'fra') 0).Ready $true
Assert-Equal (Test-TesseractLanguageOutput @('List of available languages:', 'fra') 0).Ready $false
Assert-Equal (Test-TesseractLanguageOutput @('error') 1).Ready $false
Assert-Equal (Get-OcrSetupDecision $false $false 'NO') 'Skip'
Assert-Equal (Get-OcrSetupDecision $false $false 'YES') 'Install'
Assert-Equal (Get-OcrSetupDecision $false $true '') 'Install'
Assert-Equal (Get-OcrSetupDecision $true $true 'NO') 'Ready'
$repairAction = Get-TesseractInstallAction $false 'C:\Tesseract\tesseract.exe' $true
Assert-Equal $repairAction 'RepairLanguageData'
Assert-Equal (Get-TesseractInstallAction $false $null $false) 'ManualInstall'
Assert-Equal (Get-TesseractInstallAction $false $null $true) 'InstallPackage'
Assert-Equal (Get-TesseractInstallAction $true 'C:\Tesseract\tesseract.exe' $true) 'Ready'
$failureMessage = Get-OcrFailureMessage 'WinGet could not start.'
if ($failureMessage -notmatch 'Text-based PDFs still work' -or $failureMessage -notmatch 'Repair OCR') {
    throw 'The OCR failure path must preserve text-PDF functionality and provide a repair action.'
}

$temporary = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
$null = New-Item $temporary -ItemType Directory
try {
    $file = Join-Path $temporary 'sample.txt'
    Set-Content $file 'installer test'
    $manifest = Join-Path $temporary 'SHA256.json'
    ConvertTo-Json -InputObject @(@{ path = 'sample.txt'; sha256 = (Get-FileHash $file).Hash }) | Set-Content $manifest
    Assert-PayloadIntegrity $temporary
    Set-Content $file 'changed'
    $rejected = $false
    try { Assert-PayloadIntegrity $temporary } catch { $rejected = $true }
    Assert-Equal $rejected $true
    ConvertTo-Json -InputObject @(@{ path = '..\outside.txt'; sha256 = 'invalid' }) | Set-Content $manifest
    $rejected = $false
    try { Assert-PayloadIntegrity $temporary } catch { $rejected = $true }
    Assert-Equal $rejected $true
    if ($RuntimeArchivePath) {
        $runtime = Join-Path $temporary 'private runtime with spaces'
        $python = Install-PrivatePython $RuntimeArchivePath $runtime
        Assert-Equal (Test-Path $python) $true
        $environment = Join-Path $temporary 'environment with spaces'
        Invoke-CheckedProcess $python @('-m', 'venv', $environment)
        Invoke-CheckedProcess (Join-Path $environment 'Scripts\python.exe') @('-m', 'pip', 'check')
        Assert-Equal @(Get-ChildItem $temporary -Directory -Filter '*-unpack-*').Count 0
        Write-Host 'PASS: private Python extraction and virtual environment creation with spaces in paths.'
    }
}
finally { Remove-Item $temporary -Recurse -Force }

Write-Host 'PASS: script syntax, hardware recommendations, payload checksums, and path traversal protection.'