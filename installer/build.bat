@echo off
REM Build pipeline for WhisperKey installer
REM Requires: Inno Setup 6.x installed

echo === WhisperKey Build Pipeline ===
echo.

REM Step 1: Run PyInstaller
echo [1/2] Building with PyInstaller...
python tools/build.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller build failed
    exit /b 1
)

REM Step 2: Compile Inno Setup installer
echo [2/2] Compiling installer with Inno Setup...
iscc installer/whisperkey.iss
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Inno Setup compilation failed
    exit /b 1
)

echo.
echo === Build completed successfully ===
echo Installer: dist/WhisperKey-Setup.exe
