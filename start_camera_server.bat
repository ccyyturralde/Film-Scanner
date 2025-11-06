@echo off
REM Film Scanner - Camera Server Startup Script (Windows)

echo.
echo ============================================================
echo    FILM SCANNER - Camera Server for Windows
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from python.org
    echo.
    pause
    exit /b 1
)

REM Check if gphoto2 is available (might be via WSL)
echo Checking for gphoto2...
gphoto2 --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: gphoto2 not found
    echo.
    echo For Windows, you have two options:
    echo   1. Install WSL ^(Windows Subsystem for Linux^) and gphoto2 in WSL
    echo   2. Use a camera that works with Windows drivers
    echo.
    echo Continuing anyway...
    echo.
)

REM Check if in correct directory
if not exist "camera_server.py" (
    echo ERROR: camera_server.py not found
    echo Please run this script from the Film-Scanner directory
    echo.
    pause
    exit /b 1
)

REM Check/install requirements
echo Checking Python packages...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install requirements
        echo Please run: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Starting camera server...
echo Press Ctrl+C to stop
echo.

REM Run the camera server
python camera_server.py

pause

