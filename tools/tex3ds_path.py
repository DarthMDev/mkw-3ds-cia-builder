#!/usr/bin/env python3
"""Resolve tex3ds from the active devkitPro installation on Windows or Unix."""
import os
from pathlib import Path

DEVKITPRO = Path(os.environ.get("DEVKITPRO", "/opt/devkitpro"))
TEX3DS = str(DEVKITPRO / "tools" / "bin" / ("tex3ds.exe" if os.name == "nt" else "tex3ds"))
