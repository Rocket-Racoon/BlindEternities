@echo off
REM Scheduled wrapper for omenpath price sync.
REM Register in Windows Task Scheduler to run once a day (e.g. 03:00 local).

setlocal
cd /d "%~dp0.."
if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
set "DJANGO_SETTINGS_MODULE=BlindEternities.settings.development"

"%PYTHON%" manage.py sync_market_prices --stale-hours 24 1>> logs\sync_market_prices.log 2>&1
endlocal
