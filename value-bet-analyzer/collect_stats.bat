@echo off
title Interactive Stats Collector
echo ========================================
echo   Interactive Stats Collector
echo   Navigate to Team Pages -> Auto Save
echo ========================================
echo.
cd /d "c:\Users\FX\.gemini\antigravity\playground\ancient-viking"
node src/scrapers/multi-site-scraper.js
pause
