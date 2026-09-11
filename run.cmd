@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run .\setup.cmd once before starting Tasker.
    exit /b 1
)

".venv\Scripts\python.exe" app.py %*
exit /b %errorlevel%
