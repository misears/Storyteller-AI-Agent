@echo off
echo ============================================
echo Installing Storyteller AI Python Dependencies
echo ============================================

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing core dependencies...
pip install fastapi
pip install uvicorn[standard]
pip install pydantic
pip install python-dotenv
pip install httpx
pip install openai
pip install anthropic
pip install aiohttp

echo Installing optional utilities...
pip install rich
pip install orjson

echo Writing requirements.txt...
pip freeze > requirements.txt

REM Create a desktop shortcut to launch the app
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\Storyteller AI.lnk"
set "TARGET=%~dp0launch_storyteller_ai.bat"

echo Creating desktop shortcut at %SHORTCUT%...
PowerShell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath=('%TARGET%'); $s.WorkingDirectory=('%~dp0'); $s.WindowStyle=1; $s.Description='Launch Storyteller AI'; $s.Save();"

echo ============================================
echo Installation complete!
echo A desktop shortcut was created for Storyteller AI.
echo To activate the environment later, run:
echo     venv\Scripts\activate
eecho ============================================
pause
