@echo off
setlocal EnableExtensions

REM ============================================================
REM MyInvest Review Package Builder
REM Put this .bat in the repository root, then double-click it.
REM It delegates to scripts\build_review_package.py so there is
REM only one package rule set to maintain.
REM ============================================================

cd /d "%~dp0"

echo.
echo Building MyInvest review package under temp\review_packages...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 scripts\build_review_package.py
    goto :CHECK
)

where python >nul 2>nul
if %errorlevel%==0 (
    python scripts\build_review_package.py
    goto :CHECK
)

echo ERROR: Python was not found. Please install Python or run the script from an environment with Python in PATH.
pause
exit /b 1

:CHECK
if errorlevel 1 goto :ERR

echo.
echo Done. Package and scan reports are in temp\review_packages.
echo Review SENSITIVE_CONTENT_SCAN.md inside the generated folder before sharing externally.
echo.
pause
exit /b 0

:ERR
echo.
echo ERROR: Packaging failed. Check temp\review_packages for REVIEW_PACKAGE_ERRORS.txt if a stage folder was created.
echo.
pause
exit /b 1
