@echo off
REM Build FName.exe (in-place rename)
echo ============================================
echo Building FName.exe
echo ============================================
echo (Use build_all.bat to build every exe at once.)
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build\FName" rmdir /s /q "build\FName"
if exist "FName.spec" del "FName.spec"
echo.

pyinstaller --onefile --console --name "FName" rename_files_inplace.py
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist "FName.spec" del "FName.spec"

echo.
echo Output: dist\FName.exe
echo Report: FNameReport.txt (overwritten each run)
pause
