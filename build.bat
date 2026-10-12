@echo off

rem Usage:
rem   build.bat | build.bat clean

if /i "%1" == "clean" (
    rmdir /s /q build dist 2>nul
    del /Q ssj.spec 2>nul
    exit /b 0
)

set PLATFORM=Windows
set VENV_PATH=.venv-"%PLATFORM%"
set VENV_PYTHON=%VENV_PATH%\Scripts\python.exe
set BUILD_PATH="build\%PLATFORM%"
set DIST_PATH="dist\%PLATFORM%"


if not exist "%VENV_PYTHON%" (
    python.exe -m venv %VENV_PATH% || exit /b 1
)

"%VENV_PYTHON%" -m pip install --upgrade pip || exit /b 1
"%VENV_PYTHON%" -m pip install --upgrade paramiko pyinstaller || exit /b 1

"%VENV_PYTHON%" -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --console ^
    --workpath "%BUILD_PATH%" ^
    --distpath "%DIST_PATH%" ^
    ssj.py
