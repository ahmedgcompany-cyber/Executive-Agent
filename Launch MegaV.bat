@echo off
title MegaV v2.7
chcp 65001 > nul

:: -- All single-instance + stale-process logic is now in run.py --
:: This BAT file just launches the app.

cd /d "%~dp0executive-agent-app"

:: -- Check Python -----------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python not found on this machine.
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Found: %%v

:: -- Launch silently (no persistent console window) -------------
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw run.py
) else (
    start "" python run.py
)

:: Brief pause then auto-close
timeout /t 2 /nobreak >nul
exit /b 0