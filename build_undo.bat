@echo off
REM Build FUndo.exe (undo renames from FName / FNamePro reports)
echo ============================================
echo Building FUndo.exe
echo ============================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build\FUndo" rmdir /s /q "build\FUndo"
if exist "FUndo.spec" del "FUndo.spec"
echo.

pyinstaller --onefile --console --name "FUndo" undo_renames_from_reports.py
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist "FUndo.spec" del "FUndo.spec"

echo.
echo Output: dist\FUndo.exe
echo Reads FNameReport*.txt and report*.txt in the same folder; optional --dry-run
pause
