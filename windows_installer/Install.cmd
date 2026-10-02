@echo off
title Storyteller AI Setup
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1" %*
if errorlevel 1 (
    echo Installation did not finish. Read the message above for help.
)
pause