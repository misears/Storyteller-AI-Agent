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

REM Configure OCR executable if available
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
    echo OCR enabled with Tesseract at "%TESSERACT_CMD%"
) else if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" (
    set "TESSERACT_CMD=C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    echo OCR enabled with Tesseract at "%TESSERACT_CMD%"
) else (
    echo Tesseract not found in common install paths. OCR fallback may be unavailable.
)

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
start "Backend" cmd /k "set LLM_PROVIDER=ollama && set OLLAMA_URL=http://127.0.0.1:11434 && set OLLAMA_MODEL=llama2:7b && set TESSERACT_CMD=%TESSERACT_CMD% && "%~dp0venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

set "BACKEND_HEALTH_URL=http://127.0.0.1:8000/health"
set "MAX_WAIT_SECONDS=30"
set /a WAIT_COUNT=0

echo Waiting for backend readiness on %BACKEND_HEALTH_URL%...

:wait_for_backend
powershell -NoProfile -Command "try { $resp = Invoke-WebRequest -UseBasicParsing '%BACKEND_HEALTH_URL%'; if ($resp.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto backend_ready

set /a WAIT_COUNT+=1
if %WAIT_COUNT% geq %MAX_WAIT_SECONDS% goto backend_timeout
timeout /t 1 /nobreak >nul
goto wait_for_backend

:backend_ready
echo Backend is ready. Opening browser...
start "" "http://127.0.0.1:8000"
echo All started. If the browser does not open automatically, visit http://127.0.0.1:8000
goto launcher_done

:backend_timeout
echo Backend did not become ready within %MAX_WAIT_SECONDS% seconds.
echo Check the Backend window for startup errors, then open http://127.0.0.1:8000 manually.
exit /b 1

:launcher_done
exit /b 0
