param(
    [switch]$Consent,
    [switch]$Interactive
)

. (Join-Path $PSScriptRoot 'Setup.Common.ps1')
$logs = Join-Path $env:LOCALAPPDATA 'StorytellerAI\logs'
$null = New-Item $logs -ItemType Directory -Force
Start-Transcript -Path (Join-Path $logs 'ocr-setup.log') -Append | Out-Null
try {
    $status = Get-TesseractStatus
    $answer = ''
    if (-not $status.Ready -and -not $Consent) {
        Write-Host "Scanned-PDF OCR is not ready: $($status.Detail)" -ForegroundColor Yellow
        Write-Host 'The verified package is UB-Mannheim.TesseractOCR from the WinGet community source.'
        $answer = Read-Host 'Install or repair scanned-PDF OCR now? Windows may request administrator approval. Type YES to continue'
    }
    $decision = Get-OcrSetupDecision -Ready $status.Ready -Consent $Consent -Answer $answer
    if ($decision -eq 'Ready') {
        Write-Host "Scanned-PDF OCR is ready. $($status.Detail)" -ForegroundColor Green
        Stop-Transcript | Out-Null
        exit 0
    }
    if ($decision -eq 'Skip') {
        Write-Host 'OCR setup was skipped. Text-based PDFs continue to work.'
        Stop-Transcript | Out-Null
        exit 0
    }
    Install-Tesseract
    Write-Host 'OCR setup complete. Restart Storyteller AI before importing scanned PDFs.' -ForegroundColor Green
    Stop-Transcript | Out-Null
    exit 0
}
catch {
    Write-Host (Get-OcrFailureMessage $_.Exception.Message) -ForegroundColor Red
    Write-Host "Setup log: $(Join-Path $logs 'ocr-setup.log')"
    Stop-Transcript | Out-Null
    if ($Interactive) { $null = Read-Host 'Press Enter to close' }
    exit 1
}
