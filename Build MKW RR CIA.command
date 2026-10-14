#!/bin/bash
# ==============================================================================
# Mario Kart Wii 3DS: Retro Rewind Mod - CIA Builder (macOS)
# ==============================================================================
# Double-click this script in Finder to build the Retro Rewind CIA.
#
# Prompts:
# 1. Disc Image: Drag your Mario Kart Wii (USA) ISO/WBFS (or press Return to
#    reuse existing extracted assets if you have already built previously).
# 2. Retro Rewind Folder: Drag your Retro Rewind folder (containing Config.pul,
#    Tracks/, etc.) to ingest new/updated tracks, or press Return to use the
#    previously cooked Retro Rewind pack on this computer.
# ==============================================================================

cd "$(dirname "$0")" || exit 1
[ -f tools/release/build_cia.py ] || cd ../.. || exit 1

echo "========================================================"
echo "    Mario Kart Wii 3DS - Retro Rewind Edition Builder   "
echo "========================================================"
echo ""

# Check Python version (3.11+)
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null || {
    echo "[-] Error: Python 3.11 or newer is required."
    echo "    Download it from: https://www.python.org/downloads/"
    exit 1
}

# Check if disc image is needed or already extracted
disc_needed=true
if [ -f "data/extracted/Race/Common.szs" ] && [ -f "build/itembox-retail.rel" ]; then
    disc_needed=false
fi

disc=""
if [ "$disc_needed" = true ]; then
    echo "[Step 1/2] Disc Image:"
    read -p "Drag your Mario Kart Wii (USA) ISO or WBFS here and press Return: " disc
    disc="${disc%\"}";disc="${disc#\"}";disc="${disc%\'}";disc="${disc#\'}"
    [ -f "$disc" ] || { echo "[-] No disc image found at: $disc"; exit 1; }
else
    echo "[Step 1/2] Disc Image:"
    echo "[*] Existing extracted disc assets detected."
    read -p "Press Return to use existing assets, or drag a new ISO/WBFS here: " disc
    disc="${disc%\"}";disc="${disc#\"}";disc="${disc%\'}";disc="${disc#\'}"
fi

echo ""
echo "[Step 2/2] Retro Rewind Pack:"
echo "If you have a Retro Rewind mod folder (containing Config.pul, Tracks/, etc.),"
echo "drag it here to import it. Press Return only to reuse a previously cooked pack."
read -p "Drag Retro Rewind folder here (or press Return to reuse cooked pack): " rr_pack
rr_pack="${rr_pack%\"}";rr_pack="${rr_pack#\"}";rr_pack="${rr_pack%\'}";rr_pack="${rr_pack#\'}"

if [ -n "$rr_pack" ]; then
    if [ -d "$rr_pack" ]; then
        echo "[+] Using external Retro Rewind pack: $rr_pack"
    else
        echo "[-] Folder not found at: $rr_pack."
        exit 1
    fi
else
    echo "[*] Checking for a previously cooked Retro Rewind pack."
fi

# Ensure vendor dependencies and python venv are present
[ -d vendor/gclib ] || python3 tools/bootstrap.py || exit 1
[ -x .venv/bin/python ] || {
    echo "[*] Setting up Python virtual environment..."
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
} || exit 1

echo ""
echo "[*] Building Retro Rewind 3DS CIA package..."
echo "--------------------------------------------------------"

build_args=(--require-pack)
if [ -n "$disc" ] && [ -f "$disc" ]; then
    build_args+=("$disc")
fi
if [ -n "$rr_pack" ] && [ -d "$rr_pack" ]; then
    build_args+=("--pack" "$rr_pack")
fi

PYTHONUNBUFFERED=1 .venv/bin/python tools/release/build_cia.py "${build_args[@]}" 2>&1 | tee build-cia-log.txt

if [ "${PIPESTATUS[0]}" -ne 0 ]; then
    echo "[-] Build failed. See build-cia-log.txt for details."
    exit 1
fi

echo ""
echo "========================================================"
echo "                   BUILD COMPLETE                       "
echo "========================================================"
echo "Outputs created:"
echo "  1. Full CIA:    build/release/mkw-3ds.cia"
echo "  2. Update CIA:  build/release/mkw-3ds-update.cia"
echo "  3. SD files:    build/release/sd-card/3ds/mkw-3ds/"
echo ""
echo "How to play:"
echo "  - On 3DS Console: Install 'mkw-3ds.cia' via FBI."
echo "                    For updates later, copy 'build/release/sd-card/3ds'"
echo "                    to your SD card and install 'mkw-3ds-update.cia'."
echo "  - On Citra/Azahar: Open 'build/release/mkw-3ds.cia' or install CIA."
echo "========================================================"
