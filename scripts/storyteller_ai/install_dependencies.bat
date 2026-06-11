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

echo ============================================
echo Installation complete!
echo To activate the environment later, run:
echo     venv\Scripts\activate
echo ============================================
pause
