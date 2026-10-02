Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Setup.Common.ps1')

function Assert-Equal {
    param($Actual, $Expected)
    if ($Actual -ne $Expected) { throw "Expected '$Expected', got '$Actual'." }
}

foreach ($file in Get-ChildItem $PSScriptRoot -Filter '*.ps1') {
    $tokens = $null
    $parseErrors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}

Assert-Equal (Get-RecommendedModel 64 8) 'qwen3:8b'
Assert-Equal (Get-RecommendedModel 16 0) 'qwen3:4b'
Assert-Equal (Get-RecommendedModel 4 0) 'qwen3:1.7b'

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
}
finally { Remove-Item $temporary -Recurse -Force }

Write-Host 'PASS: script syntax, hardware recommendations, payload checksums, and path traversal protection.'