@echo off
REM Film Scanner Launcher Script (Windows)
REM Easy way to launch either web or CLI version

cd /d "%~dp0"

echo.
echo ============================================================
echo    FILM SCANNER LAUNCHER
echo ============================================================
echo.
echo Which version would you like to run?
echo.
echo   1. Web Application (Browser interface)
echo   2. CLI Application (Terminal interface)
echo   3. View Configuration
echo   4. Reset Configuration
echo   5. Exit
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Starting Web Application...
    echo.
    python web_app.py
    goto end
)

if "%choice%"=="2" (
    echo.
    echo Starting CLI Application...
    echo.
    python "scanner_app_v3 test.py"
    goto end
)

if "%choice%"=="3" (
    echo.
    echo === WEB APP CONFIGURATION ===
    python web_app.py --config
    echo.
    echo === CLI APP CONFIGURATION ===
    python "scanner_app_v3 test.py" --config
    echo.
    pause
    goto end
)

if "%choice%"=="4" (
    echo.
    set /p confirm="Are you sure you want to reset configuration? (y/n): "
    if /i "%confirm%"=="y" (
        python web_app.py --reset
        echo.
        echo Configuration reset complete
        echo Next time you launch, setup will run automatically.
    ) else (
        echo Reset cancelled
    )
    echo.
    pause
    goto end
)

if "%choice%"=="5" (
    echo Goodbye!
    goto end
)

echo Invalid choice
pause

:end

