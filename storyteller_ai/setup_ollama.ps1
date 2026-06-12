# Automated Ollama Setup Script for Storyteller AI Agent
# Run this script to set up Ollama and download a model

param(
    [string]$Model = "llama2:7b",
    [string]$Action = "install"
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Storyteller AI - Ollama Setup Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if command exists
function Test-CommandExists {
    param($command)
    $null = Get-Command $command -ErrorAction SilentlyContinue
    return $?
}

# Function to check if Ollama server is running
function Test-OllamaServer {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:11434" -TimeoutSec 5 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

switch ($Action.ToLower()) {
    "install" {
        Write-Host "[1/4] Checking if Ollama is installed..." -ForegroundColor Yellow
        if (Test-CommandExists ollama) {
            Write-Host "✓ Ollama is already installed" -ForegroundColor Green
            $ollamaVersion = ollama --version
            Write-Host "      Version: $ollamaVersion" -ForegroundColor Green
        }
        else {
            Write-Host "✗ Ollama is not installed" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please install Ollama first:" -ForegroundColor Cyan
            Write-Host "  1. Visit https://ollama.ai" -ForegroundColor White
            Write-Host "  2. Download the Windows installer" -ForegroundColor White
            Write-Host "  3. Run the installer and follow instructions" -ForegroundColor White
            Write-Host "  4. Re-run this script after installation" -ForegroundColor White
            Write-Host ""
            exit 1
        }

        Write-Host ""
        Write-Host "[2/4] Checking if Ollama server is running..." -ForegroundColor Yellow
        if (Test-OllamaServer) {
            Write-Host "✓ Ollama server is running at http://127.0.0.1:11434" -ForegroundColor Green
        }
        else {
            Write-Host "✗ Ollama server is not running" -ForegroundColor Red
            Write-Host ""
            Write-Host "Starting Ollama server..." -ForegroundColor Yellow
            Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
            Write-Host "Waiting for server to start..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5

            if (Test-OllamaServer) {
                Write-Host "✓ Ollama server started successfully" -ForegroundColor Green
            }
            else {
                Write-Host "✗ Failed to start Ollama server" -ForegroundColor Red
                Write-Host "Please start it manually: ollama serve" -ForegroundColor Yellow
                exit 1
            }
        }

        Write-Host ""
        Write-Host "[3/4] Pulling model: $Model" -ForegroundColor Yellow
        Write-Host "      This may take several minutes (3-7GB download)..." -ForegroundColor Gray
        Write-Host ""
        
        # Pull the model
        ollama pull $Model

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✓ Model downloaded successfully" -ForegroundColor Green
        }
        else {
            Write-Host "✗ Failed to download model" -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "[4/4] Verifying model..." -ForegroundColor Yellow
        $models = ollama list | Select-String $Model.Split(':')[0]
        if ($models) {
            Write-Host "✓ Model is available:" -ForegroundColor Green
            Write-Host "  $models" -ForegroundColor Green
        }
        else {
            Write-Host "✗ Model verification failed" -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "======================================" -ForegroundColor Cyan
        Write-Host "Setup Complete!" -ForegroundColor Green
        Write-Host "======================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "  1. Create or update .env file with Ollama settings" -ForegroundColor White
        Write-Host "  2. Run: python -m uvicorn storyteller_ai.backend.main:app --reload" -ForegroundColor White
        Write-Host ""
        Write-Host ".env Configuration:" -ForegroundColor Cyan
        Write-Host "  LLM_PROVIDER=ollama" -ForegroundColor Gray
        Write-Host "  OLLAMA_URL=http://127.0.0.1:11434" -ForegroundColor Gray
        Write-Host "  OLLAMA_MODEL=$Model" -ForegroundColor Gray
        Write-Host ""
        Write-Host "To test locally:" -ForegroundColor Yellow
        Write-Host "  ollama run $Model" -ForegroundColor Gray
        Write-Host ""
    }

    "test" {
        Write-Host "Testing Ollama setup..." -ForegroundColor Yellow
        Write-Host ""

        if (-not (Test-CommandExists ollama)) {
            Write-Host "✗ Ollama is not installed" -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ Ollama is installed" -ForegroundColor Green

        if (-not (Test-OllamaServer)) {
            Write-Host "✗ Ollama server is not running" -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ Ollama server is running" -ForegroundColor Green

        $models = ollama list
        if ($models) {
            Write-Host "✓ Available models:" -ForegroundColor Green
            Write-Host $models -ForegroundColor Gray
        }
        else {
            Write-Host "✗ No models found" -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "All checks passed! Ollama is ready to use." -ForegroundColor Green
    }

    "start" {
        Write-Host "Starting Ollama server..." -ForegroundColor Yellow
        if (Test-OllamaServer) {
            Write-Host "✓ Ollama server is already running" -ForegroundColor Green
            exit 0
        }

        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Write-Host "Server starting..." -ForegroundColor Yellow
        
        for ($i = 1; $i -le 10; $i++) {
            Start-Sleep -Seconds 1
            if (Test-OllamaServer) {
                Write-Host "✓ Ollama server is now running at http://127.0.0.1:11434" -ForegroundColor Green
                exit 0
            }
        }

        Write-Host "✗ Failed to start server (timeout)" -ForegroundColor Red
        exit 1
    }

    "list" {
        Write-Host "Available models:" -ForegroundColor Yellow
        ollama list
    }

    "pull" {
        if ([string]::IsNullOrWhiteSpace($Model)) {
            Write-Host "Usage: .\setup_ollama.ps1 -Action pull -Model <model_name>" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Examples:" -ForegroundColor Yellow
            Write-Host "  .\setup_ollama.ps1 -Action pull -Model llama2:7b" -ForegroundColor Gray
            Write-Host "  .\setup_ollama.ps1 -Action pull -Model mistral:7b" -ForegroundColor Gray
            exit 1
        }

        Write-Host "Pulling model: $Model" -ForegroundColor Yellow
        ollama pull $Model
    }

    default {
        Write-Host "Usage: .\setup_ollama.ps1 -Action <action> [-Model <model_name>]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Actions:" -ForegroundColor Cyan
        Write-Host "  install  - Full setup (install Ollama, start server, download model)" -ForegroundColor White
        Write-Host "  test     - Test if Ollama is configured correctly" -ForegroundColor White
        Write-Host "  start    - Start Ollama server" -ForegroundColor White
        Write-Host "  list     - List available models" -ForegroundColor White
        Write-Host "  pull     - Download a specific model" -ForegroundColor White
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Yellow
        Write-Host "  .\setup_ollama.ps1 -Action install -Model llama2:7b" -ForegroundColor Gray
        Write-Host "  .\setup_ollama.ps1 -Action test" -ForegroundColor Gray
        Write-Host "  .\setup_ollama.ps1 -Action pull -Model mistral:7b" -ForegroundColor Gray
        Write-Host ""
    }
}
