@echo off
title MegaV v2.7 - Local AI Setup
echo ============================================================
echo   MegaV v2.7 - Local AI Setup (FREE, No API Key Needed)
echo ============================================================
echo.
echo This will set up Ollama so the agent can think and generate
echo responses entirely on YOUR computer, with NO internet or
echo API key required after setup.
echo.
echo Tip: the in-app first-run wizard can also pick a model for
echo you based on your hardware. Use this BAT for a quick start.
echo.

:: Check if Ollama is already installed
where ollama >nul 2>&1
if not errorlevel 1 (
    echo Ollama is already installed.
    goto :pull_models
)

echo Step 1: Download and install Ollama...
echo.
echo Opening the Ollama download page in your browser.
echo After installing, come back and press any key to continue.
echo.
start https://ollama.com/download
pause

:pull_models
echo.
echo Step 2: Downloading AI models (this may take a few minutes)...
echo.

echo [1/2] Downloading dolphin-mistral (uncensored general use, ~4GB)...
ollama pull dolphin-mistral
if errorlevel 1 (
    echo Failed to pull dolphin-mistral. Make sure Ollama is running.
    echo You can pull it manually later with:  ollama pull dolphin-mistral
    pause
    exit /b 1
)

echo.
echo [2/2] Downloading codellama (for coding tasks, ~3.8GB)...
ollama pull codellama
if errorlevel 1 (
    echo Note: codellama failed. You can pull it later with:  ollama pull codellama
)

echo.
echo ============================================================
echo   Setup complete!
echo.
echo   Ollama is now running locally on your machine.
echo   No API key or internet connection needed for AI features.
echo.
echo   Models installed:
echo     dolphin-mistral - Uncensored general tasks
echo     codellama       - Code generation and debugging
echo.
echo   Want different models? Open MegaV -^> Settings -^> AI Status
echo   to browse the full uncensored model catalog.
echo.
echo   Now double-click "Launch MegaV.bat" to start.
echo ============================================================
pause
