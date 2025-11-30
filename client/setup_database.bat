@echo off
REM Setup script for SITARA Client Database
REM Run this before starting the client for the first time

echo.
echo ============================================================
echo SITARA CLIENT DATABASE SETUP
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please ensure Python is installed and added to PATH
    pause
    exit /b 1
)

REM Try to find Python executable (prefer venv, fallback to system Python)
if exist "..\.venv\Scripts\python.exe" (
    set PYTHON_CMD=..\.venv\Scripts\python.exe
    echo Using virtual environment Python: %PYTHON_CMD%
) else (
    set PYTHON_CMD=python
    echo Using system Python
)

echo [1/3] Initializing database...
%PYTHON_CMD% init_client_db.py
if errorlevel 1 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)

echo.
echo [2/3] Loading credentials from config.env file...
REM Extract values from config.env for seeding
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="ROBOT_ID" set ROBOT_ID=%%b
    if "%%a"=="ROBOT_USERNAME" set USERNAME=%%b
    if "%%a"=="ROBOT_PASSWORD" set PASSWORD=%%b
)

if not defined ROBOT_ID set ROBOT_ID=1
if not defined USERNAME set USERNAME=deepak
if not defined PASSWORD set PASSWORD=password

echo   Robot ID: %ROBOT_ID%
echo   Username: %USERNAME%
echo   Password: ********

echo.
echo [3/3] Seeding initial data...
%PYTHON_CMD% init_client_db.py %ROBOT_ID% %USERNAME% %PASSWORD%
if errorlevel 1 (
    echo ERROR: Data seeding failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS! Client database is ready
echo ============================================================
echo.
echo You can now start the client with:
echo   python client_app.py
echo.
echo or
echo   start_client.bat
echo.
pause
