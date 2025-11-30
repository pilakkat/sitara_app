@echo off
REM SITARA Robot Client Launcher
REM 
REM Usage:
REM   start_client.bat          (Robot ID = 1)
REM   start_client.bat 2        (Robot ID = 2)
REM   start_client.bat 3 operator operator123

echo ============================================================
echo SITARA ROBOT CLIENT LAUNCHER
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check if requests is installed
python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo Starting robot client...
echo.

REM Pass all arguments to the Python script
python client_app.py %*

pause
