@echo off
title Binance Square Posting Bot - Talha Sniper
color 0A

echo ========================================================
echo    Binance Square Automated Posting Bot - Talha Sniper
echo ========================================================
echo.
echo Choose posting interval in minutes:
echo   [15] Every 15 Minutes
echo   [30] Every 30 Minutes (Recommended / Default)
echo   [45] Every 45 Minutes
echo   [60] Every 1 Hour
echo.
set /p INTERVAL="Enter interval in minutes (or press ENTER for default [30]): "

if "%INTERVAL%"=="" (
    set INTERVAL_FLAG=
    echo Using default interval: 30 minutes.
) else (
    set INTERVAL_FLAG=--interval %INTERVAL%
    echo Setting custom interval: %INTERVAL% minutes.
)

echo.
echo Starting 24/7 background scheduler...
echo Press Ctrl + C at any time to stop.
echo.

call "%~dp0python.bat" -u main.py %INTERVAL_FLAG%

pause
