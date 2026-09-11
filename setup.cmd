@echo off
setlocal
cd /d "%~dp0"

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 was not found. Install it with the Python launcher, then try again.
    echo See the Windows setup instructions in README.md.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
    echo This .venv uses another Python version. Rename that folder, then run setup again.
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.lock.txt
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip check
if errorlevel 1 exit /b 1

echo.
echo Tasker is ready. Run .\run.cmd, then open http://127.0.0.1:5050
exit /b 0
