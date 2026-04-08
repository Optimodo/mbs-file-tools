@echo off
REM Build FList.exe (file list generator)
echo ============================================
echo Building FList.exe
echo ============================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build\FList" rmdir /s /q "build\FList"
if exist "FList.spec" del "FList.spec"
echo.

pyinstaller --onefile --console --name "FList" list_files.py
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist "FList.spec" del "FList.spec"

echo.
echo Output: dist\FList.exe
echo Writes: filelist.txt
pause
