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
echo Starting Storyteller AI backend...
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

echo Storyteller AI backend has stopped.
pause
