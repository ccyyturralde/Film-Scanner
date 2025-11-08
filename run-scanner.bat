@echo off
REM Film Scanner Desktop - Quick Launch Script

title Film Scanner Desktop

echo Starting Film Scanner...
echo.

python scanner_desktop.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start scanner
    echo.
    echo Make sure you've run setup-desktop.bat first
    echo.
    pause
)

