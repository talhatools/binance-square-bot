@echo off
title Binance Square Bot - Stats and History
color 0B

cd /d "%~dp0"

echo ========================================================
echo    Binance Square Bot - Performance Stats
echo ========================================================
call "%~dp0python.bat" main.py --stats

echo.
echo ========================================================
echo    Recent Posts History
echo ========================================================
call "%~dp0python.bat" main.py --history

echo.
pause
