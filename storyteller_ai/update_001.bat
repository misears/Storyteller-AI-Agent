@echo off
echo ============================================
echo Storyteller AI - Update 001 Automation Script
echo ============================================

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

echo Installing test dependencies...
pip install pytest

echo Running bootstrap generator...
python bootstrap_backend.py

echo Copying updated validator...
copy /Y updated\state_validator.py storyteller_ai\backend\services\state_validator.py

echo Copying updated orchestrator merge logic...
copy /Y updated\orchestrator.py storyteller_ai\backend\gm_modes\orchestrator.py

echo Copying updated engine wiring...
copy /Y updated\engine_wiring.py storyteller_ai\backend\gm_modes\engine_wiring.py

echo Running test suite...
pytest -q

echo ============================================
echo Update 001 Complete
echo ============================================
pause
