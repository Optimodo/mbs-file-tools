@echo off
setlocal enabledelayedexpansion
REM Simple file list generator
REM Creates a text file with a list of all files in the current folder

:menu
cls
echo ========================================
echo        FILE LIST GENERATOR
echo ========================================
echo.
echo Choose an option:
echo.
echo   1. Include file extensions
echo   2. Exclude file extensions
echo.
echo ========================================
set /p choice="Enter your choice (1 or 2): "

if "%choice%"=="1" goto include_ext
if "%choice%"=="2" goto exclude_ext

echo.
echo Invalid choice. Please try again.
timeout /t 2 >nul
goto menu

:include_ext
REM Create file list with extensions (exclude this batch file and output file)
dir /b | findstr /v /i "list_files.bat filelist.txt" > filelist.txt
goto done

:exclude_ext
REM Create temporary files for processing
set tempfile=%temp%\filelist_temp_%random%.txt
set uniquefile=%temp%\filelist_unique_%random%.txt

REM First: List all files with extensions (like option 1)
dir /b | findstr /v /i "list_files.bat filelist.txt" > filelist.txt

REM Add blank line
echo. >> filelist.txt

REM Collect all filenames without extensions and sort
for %%F in (*.*) do (
    if /i not "%%F"=="list_files.bat" if /i not "%%F"=="filelist.txt" (
        echo %%~nF
    )
) | sort > %tempfile%

REM Remove duplicates - write each unique name to temp file
set prevname=
for /f "delims=" %%A in (%tempfile%) do (
    findstr /x /c:"%%A" %uniquefile% >nul 2>&1
    if errorlevel 1 (
        echo %%A >> %uniquefile%
    )
)

REM Append unique list to output
type %uniquefile% >> filelist.txt

REM Clean up temp files
del %tempfile% 2>nul
del %uniquefile% 2>nul

goto done

:done
echo.
echo ========================================
echo File list created: filelist.txt
echo ========================================
echo.
echo Location: %CD%
echo.
pause

