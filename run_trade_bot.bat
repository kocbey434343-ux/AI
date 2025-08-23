@echo off
rem ===============================================================
rem  Unified Trade Bot Launcher
rem  Usage: run_trade_bot [console|silent|help]
rem  - console (default): runs with standard console (shows stdout)
rem  - silent            : runs in background (pythonw, no console)
rem  - help              : show usage
rem ===============================================================
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"
set SCRIPT_DIR=%~dp0
set PYTHONPATH=%SCRIPT_DIR%

rem ---- Parse mode ----
set MODE=console
if /I "%1"=="silent" set MODE=silent
if /I "%1"=="-s" set MODE=silent
if /I "%1"=="console" set MODE=console
if /I "%1"=="help" goto :usage
if /I "%1"=="/??" goto :usage
if /I "%1"=="/?" goto :usage

rem ---- Activate venv if present ----
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

set VENV_PY="%SCRIPT_DIR%.venv\Scripts\python.exe"
set VENV_PYW="%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
set PYTHON_CMD=python
if exist %VENV_PY% set PYTHON_CMD=%VENV_PY%

rem ---- Silent mode ----
if /I "%MODE%"=="silent" (
	echo [INFO] Silent mod: arka planda baslatiliyor...
	if exist %VENV_PYW% (
		start "TradeBot" /B %VENV_PYW% src\main.py
	) else (
		start "TradeBot" /B %PYTHON_CMD% src\main.py
	)
	echo [INFO] Calisiyor. Loglar: data\logs
	goto :eof
)

rem ---- Console mode ----
echo [INFO] Console mod basliyor...
%PYTHON_CMD% src\main.py
if errorlevel 1 (
	echo.
	echo [ERROR] Uygulama hata ile cikti. Loglar: data\logs
) else (
	echo.
	echo [INFO] Program sonlandi veya pencere kapatildi. Loglar: data\logs
)
pause
goto :eof

:usage
echo Kullanım: run_trade_bot [console^|silent]
echo    console (varsayilan) : Konsolda calistirir ve cikis loglarini gosterir
echo    silent               : Arka planda (pythonw) calistirir, sadece loglara yazar
echo Ornek: run_trade_bot silent
pause
goto :eof

endlocal
