@echo off
REM SafeKeep Build Script
REM Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
echo Installing dependencies...
pip install -r requirements.txt
echo Building SafeKeep executable...
pyinstaller --onefile --windowed --name SafeKeep --icon=assets/icon.ico main.py
echo Build complete! Find SafeKeep.exe in dist/ folder.
pause
