#!/bin/bash

# Gamma Test Runner Launcher
echo "🚀 Starting Gamma Test Runner..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements if needed
if [ ! -f ".venv/pip_installed" ]; then
    echo "📦 Installing requirements..."
    pip install -r requirements_gui.txt
    touch .venv/pip_installed
fi

# Run the GUI
echo "✅ Starting GUI..."
python3 gui.py
