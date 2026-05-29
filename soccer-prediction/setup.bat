@echo off
REM Soccer Prediction Bot - Windows Setup Script
REM Automatically installs Python and dependencies

echo ============================================================
echo  SOCCER PREDICTION BOT - Windows Setup
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed!
    echo.
    echo Please install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python is installed
python --version
echo.

REM Check if pip is available
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip is not available
    echo Installing pip...
    python -m ensurepip --upgrade
)

echo [OK] pip is available
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo Installing dependencies (this may take 5-10 minutes)...
echo.
python -m pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install dependencies
    echo.
    echo Try running as Administrator or install manually:
    echo python -m pip install pandas numpy scikit-learn xgboost lightgbm
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Installation Complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Get API key from https://www.api-football.com/
echo 2. Edit config.py and add your API key
echo 3. Run demo: python demo.py
echo 4. Run full pipeline: python main.py --step full
echo.
echo Read SETUP_WINDOWS.md for detailed instructions.
echo.
pause
