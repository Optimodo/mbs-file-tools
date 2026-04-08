@echo off
REM Master build script - builds all standalone exes (short names for deep paths)
echo ============================================
echo Building All Standalone EXEs
echo ============================================
echo.
echo This will build:
echo   1. FName.exe   (in-place rename)
echo   2. FList.exe   (file list generator)
echo   3. FNamePro.exe (doc-ref list + rename, report.txt)
echo   4. FUndo.exe   (undo renames from reports)
echo.
echo ============================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

if exist "build" (
    echo Cleaning build directory...
    rmdir /s /q build
)
if exist "*.spec" (
    echo Cleaning spec files...
    del *.spec
)
echo.

echo ============================================
echo [1/4] Building FName.exe...
echo ============================================
pyinstaller --onefile --console --name "FName" rename_files_inplace.py
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for FName.exe!
    pause
    exit /b 1
)
echo.

echo ============================================
echo [2/4] Building FList.exe...
echo ============================================
pyinstaller --onefile --console --name "FList" list_files.py
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for FList.exe!
    pause
    exit /b 1
)
echo.

echo ============================================
echo [3/4] Building FNamePro.exe...
echo ============================================
pyinstaller --onefile --console --name "FNamePro" docref_rename_list.py
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for FNamePro.exe!
    pause
    exit /b 1
)
echo.

echo ============================================
echo [4/4] Building FUndo.exe...
echo ============================================
pyinstaller --onefile --console --name "FUndo" undo_renames_from_reports.py
if errorlevel 1 (
    echo.
    echo ERROR: Build failed for FUndo.exe!
    pause
    exit /b 1
)
echo.

if exist "*.spec" (
    del *.spec
)

echo.
echo ============================================
echo All builds complete!
echo ============================================
echo.
echo Executables created in dist folder:
echo   - FName.exe
echo   - FList.exe
echo   - FNamePro.exe
echo   - FUndo.exe
echo.
echo ============================================
pause
