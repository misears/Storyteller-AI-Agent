@echo off
setlocal

REM Change to the repository root folder
cd /d "%~dp0"

REM Check for the virtual environment
if not exist "venv\Scripts\activate" (
    echo Virtual environment not found.
    echo Please run install_dependencies.bat first.
    pause
    exit /b 1
)

call "venv\Scripts\activate"
echo.
echo Starting Storyteller AI with Ollama and Llama2...

REM Verify Ollama is installed
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Ollama is not installed or not found in PATH.
    echo Install Ollama from https://ollama.ai and rerun this script.
    pause
    exit /b 1
)

echo Checking Ollama server...
powershell -NoProfile -Command "try { $req = [System.Net.WebRequest]::Create('http://127.0.0.1:11434'); $req.Timeout = 2000; $resp = $req.GetResponse(); $resp.Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Ollama server is not running. Starting Ollama server...
    start "Ollama" cmd /k "ollama serve"
    timeout /t 5 /nobreak >nul
) else (
    echo Ollama server already running.
)

set "MODEL=llama2:7b"
echo.
echo Checking for local model %MODEL%...
ollama list | findstr /C:"%MODEL%" >nul 2>&1
if errorlevel 1 (
    echo Model %MODEL% was not found locally.
    echo Downloading %MODEL% now. This may take several minutes...
    ollama pull %MODEL%
    if errorlevel 1 (
        echo Failed to download the Ollama model %MODEL%.
        pause
        exit /b 1
    )
) else (
    echo Local model %MODEL% is installed.
)

echo.
echo Starting backend server...
start "Backend" cmd /k "set LLM_PROVIDER=ollama && set OLLAMA_URL=http://127.0.0.1:11434 && set OLLAMA_MODEL=llama2:7b && "%~dp0venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

echo Waiting briefly before opening the browser...
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000"

echo All started. If the browser does not open automatically, visit http://127.0.0.1:8000
exit /b 0
