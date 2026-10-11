@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if not exist "tools\release\build_cia.py" (
  cd ..\.. || goto :error
)

where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.11 or newer from https://www.python.org/downloads/
  echo During installation, enable the Python Launcher and add Python to PATH.
  pause
  exit /b 1
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js LTS is required: https://nodejs.org/
  pause
  exit /b 1
)
where git >nul 2>nul
if errorlevel 1 (
  echo Git for Windows is required: https://git-scm.com/download/win
  pause
  exit /b 1
)
rem If DEVKITPRO is set to a Unix path such as /opt/devkitpro, replace it
rem with the Windows path used by the extracted devkitPro/MSYS2 setup.
if not exist "%DEVKITPRO%\devkitARM\bin\arm-none-eabi-gcc.exe" (
  if exist "%USERPROFILE%\Downloads\cia\devkitPro\devkitARM\bin\arm-none-eabi-gcc.exe" (
    set "DEVKITPRO=%USERPROFILE%\Downloads\cia\devkitPro"
  )
)
if not exist "%DEVKITPRO%\devkitARM\bin\arm-none-eabi-gcc.exe" (
  echo Could not find the ARM compiler under "%DEVKITPRO%".
  echo Expected it at "%USERPROFILE%\Downloads\cia\devkitPro\devkitARM\bin\arm-none-eabi-gcc.exe".
  echo Check that the extracted devkitPro folder is still in Downloads\cia.
  pause
  exit /b 1
)
rem Add the devkitPro tools and the MSYS2 usr/bin directory used by this setup.
set "PATH=%DEVKITPRO%\devkitARM\bin;%DEVKITPRO%\tools\bin;%USERPROFILE%\Downloads\cia\usr\bin;%DEVKITPRO%\usr\bin;%PATH%"

set /p "DISC=Enter or drag the path to your Mario Kart Wii USA ISO/WBFS, then press Enter: "
set "DISC=%DISC:"=%"
if not exist "!DISC!" (
  echo Could not find disc image: !DISC!
  pause
  exit /b 1
)

if not exist "vendor\gclib" (
  echo Downloading pinned source dependencies...
  py -3 tools\bootstrap.py
  if errorlevel 1 goto :error
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment and installing packages...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

echo Building CIA. This can take a long time; keep this window open.
".venv\Scripts\python.exe" -u tools\release\build_cia.py "%DISC%" > build-cia-log.txt 2>&1
set "RESULT=%ERRORLEVEL%"
type build-cia-log.txt
if not "%RESULT%"=="0" (
  echo.
  echo Build failed. Share build-cia-log.txt if you need help.
  pause
  exit /b %RESULT%
)
echo.
echo Build finished. Check build\release\mkw-3ds.cia
echo Log saved to build-cia-log.txt
pause
exit /b 0

:error
echo.
echo Setup or build failed. Review the messages above.
pause
exit /b 1
