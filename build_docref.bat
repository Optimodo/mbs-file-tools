@echo off
REM Build FNamePro.exe (doc-ref rename + report.txt)
echo ============================================
echo Building FNamePro.exe
echo ============================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build\FNamePro" rmdir /s /q "build\FNamePro"
if exist "FNamePro.spec" del "FNamePro.spec"
echo.

pyinstaller --onefile --console --name "FNamePro" docref_rename_list.py
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist "FNamePro.spec" del "FNamePro.spec"

echo.
echo Output: dist\FNamePro.exe
echo Report: report.txt (overwritten each run)
echo Optional: docref_whitelist.json next to exe
pause
