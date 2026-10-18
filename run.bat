@echo off
title Binance Square Bot - Single Post
color 0E

cd /d "%~dp0"
echo Running one live posting cycle to Binance Square...
echo.

call "%~dp0python.bat" main.py --run-once --force %*

echo.
echo Cycle finished.
pause
