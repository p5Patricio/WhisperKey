@echo off
REM Build pipeline for WhisperKey installer
REM Requires: Inno Setup 6.x installed (iscc on PATH)

echo === WhisperKey Build Pipeline ===
echo.

REM Use the project's virtualenv Python so all deps + PyInstaller are available.
set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo ERROR: venv no encontrado en %PY%
    echo Crea el entorno e instala dependencias antes de buildear.
    exit /b 1
)

REM Step 0: Ensure PyInstaller is installed in the venv.
"%PY%" -c "import PyInstaller" 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo Installing PyInstaller...
    "%PY%" -m pip install pyinstaller
)

REM Step 1: Run PyInstaller
echo [1/2] Building with PyInstaller...
"%PY%" tools/build.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller build failed
    exit /b 1
)

REM Step 2: Locate the Inno Setup compiler (PATH, or v7/v6 machine/per-user dirs).
REM winget without admin installs per-user under %LOCALAPPDATA%\Programs.
set "ISCC="
where iscc >NUL 2>&1 && set "ISCC=iscc"
for %%D in (
    "%ProgramFiles%\Inno Setup 7"
    "%ProgramFiles(x86)%\Inno Setup 7"
    "%LOCALAPPDATA%\Programs\Inno Setup 7"
    "%ProgramFiles%\Inno Setup 6"
    "%ProgramFiles(x86)%\Inno Setup 6"
    "%LOCALAPPDATA%\Programs\Inno Setup 6"
) do if not defined ISCC if exist "%%~D\ISCC.exe" set "ISCC=%%~D\ISCC.exe"
if not defined ISCC (
    echo ERROR: Inno Setup no encontrado. Instalalo desde https://jrsoftware.org/isdl.php
    exit /b 1
)

echo [2/2] Compiling installer with Inno Setup...
"%ISCC%" installer/whisperkey.iss
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Inno Setup compilation failed
    exit /b 1
)

echo.
echo === Build completed successfully ===
echo Installer: dist/WhisperKey-Setup.exe
