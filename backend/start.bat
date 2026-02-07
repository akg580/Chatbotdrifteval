@echo off
REM Compliance Monitor - Startup Script for Windows

echo ==================================================
echo Starting Compliance Monitor
echo ==================================================

REM Check if we're in the right directory
if not exist "app.py" (
    echo Error: Please run this script from the backend\ directory
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo No .env file found
    echo Creating from template...
    copy .env.example .env
    echo.
    echo Please edit .env and add your Anthropic API key
    echo Then run this script again
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import flask, anthropic" 2>nul
if errorlevel 1 (
    echo Dependencies not installed
    echo Installing now...
    pip install -r requirements.txt
)

REM Run the app
echo.
echo Starting server...
echo.
python app.py

pause
