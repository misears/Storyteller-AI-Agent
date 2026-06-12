@echo off
echo ============================================
echo Installing Storyteller AI Python Dependencies
echo ============================================

REM Ensure the script runs from the repository root
cd /d "%~dp0"

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call "%~dp0venv\Scripts\activate"

echo Upgrading pip...
"%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip

echo Installing core dependencies...
"%~dp0venv\Scripts\python.exe" -m pip install fastapi
"%~dp0venv\Scripts\python.exe" -m pip install "uvicorn[standard]"
"%~dp0venv\Scripts\python.exe" -m pip install pydantic
"%~dp0venv\Scripts\python.exe" -m pip install python-dotenv
"%~dp0venv\Scripts\python.exe" -m pip install httpx
"%~dp0venv\Scripts\python.exe" -m pip install openai
"%~dp0venv\Scripts\python.exe" -m pip install anthropic
"%~dp0venv\Scripts\python.exe" -m pip install aiohttp

echo Installing optional utilities...
"%~dp0venv\Scripts\python.exe" -m pip install rich
"%~dp0venv\Scripts\python.exe" -m pip install orjson

echo Writing requirements.txt...
"%~dp0venv\Scripts\python.exe" -m pip freeze > requirements.txt

REM Create a desktop shortcut to launch the app
REM Create a desktop shortcut to launch the app (resolve Desktop path reliably)
set "TARGET=%~dp0launch_storyteller_ai.bat"

echo Creating desktop shortcut on the current user's Desktop...
PowerShell -NoProfile -Command "
	$desktop = [Environment]::GetFolderPath('Desktop');
	$shortcutPath = Join-Path $desktop 'Storyteller AI.lnk';
	$target = '%TARGET%';
	$working = '%~dp0';
	if (-not (Test-Path $desktop)) { New-Item -ItemType Directory -Path $desktop | Out-Null }
	$s = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath);
	$s.TargetPath = $target;
	$s.WorkingDirectory = $working;
	$s.WindowStyle = 1;
	$s.Description = 'Launch Storyteller AI';
	$s.Save();
"
if %ERRORLEVEL% EQU 0 (
	echo Shortcut created at: %USERPROFILE%\Desktop\Storyteller AI.lnk
) else (
	echo Warning: failed to create desktop shortcut (you can create one manually from launch_storyteller_ai.bat)
)

echo ============================================
echo Installation complete!
echo A desktop shortcut was created for Storyteller AI.
echo To activate the environment later, run:
echo     venv\Scripts\activate
echo ============================================
pause
