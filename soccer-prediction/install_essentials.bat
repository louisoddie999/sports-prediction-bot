@echo off
REM Quick Install Script - Installs only essential packages first
echo ============================================================
echo  Installing Essential Packages...
echo ============================================================
echo.
echo This will install: requests, pandas, numpy
echo.

python -m pip install requests pandas numpy

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo  Essential packages installed!
    echo ============================================================
    echo.
    echo Now testing your setup...
    echo.
    python test_setup.py
) else (
    echo.
    echo [ERROR] Installation failed
    echo.
    echo Try running as Administrator or check your internet connection
    echo.
)

pause
