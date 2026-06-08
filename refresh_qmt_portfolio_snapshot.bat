@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Refreshing QMT read-only portfolio snapshot...
echo.
echo Privacy: this writes ratios, cost price, current price, day change pct and pnl pct only.
echo It does NOT write market value, cash amount, share count, profit amount, or full account id.
echo.
echo Prerequisite: QMT must be logged in and started with "independent trading" enabled.
echo.

py -3.11 scripts\qmt_portfolio_snapshot.py

if errorlevel 1 (
  echo.
  echo Snapshot refresh failed. Check QMT login, independent trading mode, account permission, and Python 3.11.
  pause
)
