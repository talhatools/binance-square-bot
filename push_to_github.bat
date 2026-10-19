@echo off
title Push Binance Bot to GitHub
echo ========================================================
echo Pushing Binance Square Bot to GitHub (talhatools)...
echo ========================================================
cd /d "%~dp0"
git push -u origin main
echo.
echo ========================================================
echo Push complete!
echo ========================================================
pause
