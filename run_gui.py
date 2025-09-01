#!/usr/bin/env python3
"""
Gamma Test Runner Launcher
Simple Python script to run the GUI application
"""

import os
import sys
import subprocess
import platform

def main():
    print("🚀 Starting Gamma Test Runner...")
    
    # Check if virtual environment exists
    venv_path = ".venv"
    if not os.path.exists(venv_path):
        print("❌ Virtual environment not found. Creating one...")
        try:
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
            print("✅ Virtual environment created successfully!")
        except subprocess.CalledProcessError:
            print("❌ Failed to create virtual environment")
            return
    
    # Determine activation script based on platform
    if platform.system() == "Windows":
        activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
        python_exe = os.path.join(venv_path, "Scripts", "python.exe")
    else:
        activate_script = os.path.join(venv_path, "bin", "activate")
        python_exe = os.path.join(venv_path, "bin", "python")
    
    # Check if requirements are installed
    pip_installed_flag = os.path.join(venv_path, "pip_installed")
    if not os.path.exists(pip_installed_flag):
        print("📦 Installing requirements...")
        try:
            if platform.system() == "Windows":
                subprocess.run([python_exe, "-m", "pip", "install", "-r", "requirements_gui.txt"], check=True)
            else:
                subprocess.run([python_exe, "-m", "pip", "install", "-r", "requirements_gui.txt"], check=True)
            
            # Create flag file
            with open(pip_installed_flag, 'w') as f:
                f.write("installed")
            print("✅ Requirements installed successfully!")
        except subprocess.CalledProcessError:
            print("❌ Failed to install requirements")
            return
    
    # Run the GUI
    print("✅ Starting GUI...")
    try:
        if platform.system() == "Windows":
            subprocess.run([python_exe, "gui.py"])
        else:
            subprocess.run([python_exe, "gui.py"])
    except KeyboardInterrupt:
        print("\n👋 GUI closed by user")
    except Exception as e:
        print(f"❌ Error running GUI: {e}")

if __name__ == "__main__":
    main()
