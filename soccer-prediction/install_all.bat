@echo off
REM Complete Installation Script - Installs all required packages
echo ============================================================
echo  Installing ALL Required Packages
echo ============================================================
echo.
echo This will install all dependencies for the Soccer Prediction Bot
echo Estimated time: 10-15 minutes
echo.
pause

echo.
echo [1/3] Installing core packages...
py -m pip install --upgrade pip
py -m pip install requests pandas numpy python-dotenv

echo.
echo [2/3] Installing machine learning libraries...
py -m pip install scikit-learn xgboost lightgbm optuna

echo.
echo [3/3] Installing additional utilities...
py -m pip install python-telegram-bot ratelimit tqdm seaborn matplotlib

echo.
echo ============================================================
echo  Installation Complete!
echo ============================================================
echo.
echo Testing your setup...
echo.
py test_setup.py

echo.
echo ============================================================
echo  All Done! You can now run:
echo ============================================================
echo.
echo   py demo.py              (Demo with mock data)
echo   py main.py --step collect  (Collect real data - takes hours!)
echo   py telegram_notifier.py    (Test Telegram)
echo.
pause
