@echo off
REM CR-0073: Headless Runner Startup Script for Windows
REM Trade bot headless modda başlatma

echo ========================================
echo     Trade Bot Headless Runner
echo ========================================

REM Activate environment if exists
if exist "activate_env.bat" (
    echo Activating Python environment...
    call activate_env.bat
) else (
    echo Warning: activate_env.bat not found, using system Python
)

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python or activate environment.
    pause
    exit /b 1
)

echo Starting Trade Bot in headless mode...
echo Press Ctrl+C to stop gracefully

REM Run headless trader with arguments
python src/headless_runner.py %*

echo.
echo Headless runner stopped.
if "%1" neq "--no-pause" pause
