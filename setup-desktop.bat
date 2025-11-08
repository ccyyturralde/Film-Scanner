@echo off
REM Film Scanner Desktop - Windows Setup Script
REM Installs Python dependencies automatically

echo =========================================
echo Film Scanner Desktop - Setup
echo =========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.9 or newer from python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found!
    echo Please reinstall Python with pip included
    pause
    exit /b 1
)

echo [OK] pip found
echo.

REM Install dependencies
echo Installing dependencies...
echo.
pip install -r requirements-desktop.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed!
    echo Please check the error messages above
    pause
    exit /b 1
)

echo.
echo =========================================
echo [SUCCESS] Setup complete!
echo =========================================
echo.
echo To run the Film Scanner:
echo   python scanner_desktop.py
echo.
echo Or double-click: run-scanner.bat
echo.
pause

