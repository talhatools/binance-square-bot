@echo off
set "PY_CMD="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else if exist "C:\Users\tabu3\AppData\Local\Programs\Python311\python.exe" (
    set "PY_CMD=C:\Users\tabu3\AppData\Local\Programs\Python311\python.exe"
) else (
    set "PY_CMD=python"
)
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
"%PY_CMD%" %*
