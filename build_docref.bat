@echo off
REM Build FileRenamerPro.exe (doc-ref rename + report.txt)
echo ============================================
echo Building FileRenamerPro.exe
echo ============================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build\FileRenamerPro" rmdir /s /q "build\FileRenamerPro"
if exist "FileRenamerPro.spec" del "FileRenamerPro.spec"
if exist "build\FNamePro" rmdir /s /q "build\FNamePro"
if exist "FNamePro.spec" del "FNamePro.spec"

pyinstaller --onefile --console --name "FileRenamerPro" docref_rename_list.py
if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist "FileRenamerPro.spec" del "FileRenamerPro.spec"
if exist "dist\FNamePro.exe" del "dist\FNamePro.exe"

echo.
echo Output: dist\FileRenamerPro.exe
echo ============================================
pause
