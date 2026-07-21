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

echo Starting Storyteller AI backend...
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

echo Storyteller AI backend has stopped.
pause
