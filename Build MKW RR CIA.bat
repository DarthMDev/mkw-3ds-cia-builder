@echo off
rem ==============================================================================
rem Mario Kart Wii 3DS: Retro Rewind Mod - CIA Builder (Windows)
rem ==============================================================================
rem Double-click this script to build the Retro Rewind CIA.
rem
rem Needs devkitPro (3DS tools), Python 3.11+, Node.js LTS and Git.
rem
rem Prompts:
rem 1. Disc Image: Drag your Mario Kart Wii (USA) ISO/WBFS (or press Enter to
rem    reuse existing extracted assets if you have already built previously).
rem 2. Retro Rewind Folder: Drag your Retro Rewind folder (containing Config.pul,
rem    Tracks\, etc.) to ingest new/updated tracks, or press Enter to use the
rem    built-in/pre-cooked Retro Rewind pack in this repository.
rem ==============================================================================

setlocal
cd /d "%~dp0"

echo ========================================================
echo     Mario Kart Wii 3DS - Retro Rewind Edition Builder   
echo ========================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" || goto :nopython
where git >nul 2>nul || (echo [-] Git is needed: https://git-scm.com/download/win & goto :end)
where node >nul 2>nul || (echo [-] Node.js LTS is needed: https://nodejs.org & goto :end)

set "disc="
set "has_extracted=0"
if exist "data\extracted\Race\Common.szs" if exist "build\itembox-retail.rel" set "has_extracted=1"

echo [Step 1/2] Disc Image:
if "%has_extracted%"=="1" (
    echo [*] Existing extracted disc assets detected.
    set /p "disc=Press Enter to use existing assets, or drag a new ISO/WBFS here: "
) else (
    set /p "disc=Drag your Mario Kart Wii (USA) disc image here and press Enter: "
    if not defined disc goto :nodisc
)

if defined disc (
    set "disc=%disc:"=%"
    if not exist "%disc%" goto :nodisc
)

echo.
echo [Step 2/2] Retro Rewind Pack (Optional):
echo If you have a Retro Rewind mod folder (containing Config.pul, Tracks\, etc.),
echo drag it here to ingest it. Otherwise, press Enter to use the bundled pack.
set "rr_pack="
set /p "rr_pack=Drag Retro Rewind folder here (or press Enter for bundled pack): "

if defined rr_pack (
    set "rr_pack=%rr_pack:"=%"
    if exist "%rr_pack%\" (
        echo [+] Using external Retro Rewind pack: "%rr_pack%"
    ) else (
        echo [-] Folder not found at: "%rr_pack%". Falling back to bundled pack.
        set "rr_pack="
    )
) else (
    echo [*] Using bundled Retro Rewind pack.
)

if not exist "vendor\gclib" (%PY% tools\bootstrap.py || goto :end)
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up Python virtual environment...
    %PY% -m venv .venv || goto :end
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :end
)

set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "MKW_DISC=%disc%"
set "MKW_PACK=%rr_pack%"

echo.
echo [*] Building Retro Rewind 3DS CIA package...
echo --------------------------------------------------------

powershell -NoProfile -ExecutionPolicy Bypass -Command "$argsList = @(); if ($env:MKW_DISC) { $argsList += $env:MKW_DISC }; if ($env:MKW_PACK) { $argsList += '--pack'; $argsList += $env:MKW_PACK }; Set-Content -Path 'build-cia-log.txt' -Value $null -Encoding UTF8; & '.venv\Scripts\python.exe' 'tools\release\build_cia.py' @argsList 2>&1 | ForEach-Object { $line=$_.ToString(); $line; Add-Content -Path 'build-cia-log.txt' -Value $line -Encoding UTF8 }"

echo.
echo ========================================================
echo                    BUILD COMPLETE                       
echo ========================================================
echo Outputs created:
echo   1. Full CIA:    build\release\mkw-3ds.cia
echo   2. Update CIA:  build\release\mkw-3ds-update.cia
echo   3. SD files:    build\release\sd-card\3ds\mkw-3ds\
echo.
echo How to play:
echo   - On 3DS Console: Install 'mkw-3ds.cia' via FBI.
echo                     For updates later, copy 'build\release\sd-card\3ds'
echo                     to your SD card and install 'mkw-3ds-update.cia'.
echo   - On Citra/Azahar: Open 'build\release\mkw-3ds.cia' or install CIA.
echo ========================================================
goto :end

:nopython
echo [-] Python 3.11 or newer is needed: https://www.python.org/downloads/ (tick "Add python.exe to PATH")
goto :end
:nodisc
echo [-] No disc image at: "%disc%"
:end
pause
