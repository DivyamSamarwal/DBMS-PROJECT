@echo off
REM Simple starter for Windows (cmd)
REM - Creates a virtualenv (.venv) if missing
REM - Installs requirements from requirements.txt if present
REM - Seeds demo data
REM - Starts the Flask dev server

SETLOCAL ENABLEDELAYEDEXPANSION
echo Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
	echo Python not found in PATH. Please install Python and try again.
	exit /b 1
)

if not exist .venv (
	echo Creating virtual environment in .venv...
	python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip >nul

if exist requirements.txt (
	echo Installing requirements from requirements.txt...
	pip install -r requirements.txt
)

echo Seeding demo data (this may be skipped if you prefer)...
python .\scripts\seed_demo.py

echo Starting Flask development server...
python .\app.py

ENDLOCAL
