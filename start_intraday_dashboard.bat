@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Starting MyInvest intraday battle map...
echo.
echo Prerequisite: QMT must be logged in and started with "independent trading" enabled.
echo.

py -3.11 scripts\intraday_dashboard.py

if errorlevel 1 (
  echo.
  echo Battle map exited with an error. Check QMT login, independent trading mode, and Python 3.11.
  pause
)
