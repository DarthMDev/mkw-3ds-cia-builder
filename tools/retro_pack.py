"""Source location shared by the Retro Rewind skin cookers."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIR = Path(os.environ.get('MKW_RR_PACK', ROOT / 'RetroRewind')) / 'Character'
