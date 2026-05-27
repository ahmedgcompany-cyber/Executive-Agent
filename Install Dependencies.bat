@echo off
title MegaV v2.7 - Install Dependencies
chcp 65001 > nul
echo.
echo ============================================================
echo   MegaV v2.7  -  Installing Dependencies
echo ============================================================
echo.

:: -- Check Python --------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on this machine.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Found: %%v

cd /d "%~dp0executive-agent-app"

echo.
echo [1/2] Installing all Python packages from requirements.txt ...
echo       (this is the single source of truth — pinned versions)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo [2/2] Installing Playwright Chromium browser ...
python -m playwright install chromium
if errorlevel 1 (
    echo  WARNING: Playwright install had issues - browser features may be limited.
)

echo.
echo ============================================================
echo   All done!  You can now launch MegaV.
echo.
echo   Double-click:  Launch MegaV.bat
echo   Or use:        Launch MegaV.lnk  (desktop shortcut)
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo !! pip install failed. Try running this script as Administrator,
echo    or check your internet connection and try again.
echo.
pause
exit /b 1
