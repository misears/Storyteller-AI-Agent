@echo off
setlocal

REM Build a frozen Windows executable for Storyteller AI.
REM This script installs PyInstaller in the project venv, then runs the spec file.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows_exe.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo Build failed.
    exit /b %ERRORLEVEL%
)

echo.
echo Build finished successfully.
endlocal
