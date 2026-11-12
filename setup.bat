@echo off
title Binance Square Posting Bot - Setup Wizard
color 0B

cd /d "%~dp0"
echo ========================================================
echo   Binance Square Automated Posting Bot - Quick Setup
echo ========================================================
echo.

call "%~dp0python.bat" scripts\setup_wizard.py

pause
