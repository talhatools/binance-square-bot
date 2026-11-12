@echo off
title Binance Square Bot - Export Client Package
color 0A

cd /d "%~dp0"
echo ========================================================
echo    Packaging Clean Client Distribution ZIP
echo ========================================================
echo.

call "%~dp0python.bat" scripts\package_for_client.py

pause
