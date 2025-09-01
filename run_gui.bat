@echo off
echo 🚀 Starting BerkinWinds Test Runner...

REM Check if virtual environment exists
if not exist ".venv" (
    echo ❌ Virtual environment not found. Creating one...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install requirements if needed
if not exist ".venv\pip_installed" (
    echo 📦 Installing requirements...
    pip install -r requirements_gui.txt
    type nul > .venv\pip_installed
)

REM Run the GUI
echo ✅ Starting GUI...
python gui.py

pause
