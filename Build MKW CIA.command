#!/bin/bash
# macOS: double-click, then drag your Mario Kart Wii (USA) ISO or WBFS into the window.
# Works from the top of the builder folder or from tools/release.
cd "$(dirname "$0")" || exit 1
[ -f tools/release/build_cia.py ] || cd ../.. || exit 1
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null || { echo "Python 3.11 or newer is needed: https://www.python.org/downloads/"; exit 1; }
# read without -r undoes the backslashes Terminal adds to a dragged path ("\ ", "\(").
read -p "Drag your Mario Kart Wii (USA) disc image here and press Return: " disc
disc="${disc%\"}";disc="${disc#\"}";disc="${disc%\'}";disc="${disc#\'}"
[ -f "$disc" ] || { echo "No disc image at: $disc"; exit 1; }
[ -d vendor/gclib ] || python3 tools/bootstrap.py || exit 1
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; } || exit 1
PYTHONUNBUFFERED=1 .venv/bin/python tools/release/build_cia.py "$disc" 2>&1 | tee build-cia-log.txt
echo "Log: $(pwd)/build-cia-log.txt"
