#!/usr/bin/env python3
"""Cook Retro Rewind in-race character skin models and animation banks."""

import io
import json
import os
import shutil
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'vendor/gclib'))
from gclib.yaz0_yay0 import Yaz0
from cook_model import cook

DRIVERS = [
    ('mr', 'mario'),
    ('lg', 'luigi'),
    ('pc', 'peach'),
    ('ys', 'yoshi'),
    ('bmr', 'baby_mario'),
    ('bpc', 'baby_peach'),
    ('ko', 'toad'),
    ('nk', 'koopa_troopa'),
    ('wr', 'wario'),
    ('wl', 'waluigi'),
    ('dk', 'donkey_kong'),
    ('kp', 'bowser'),
    ('bds', 'baby_daisy'),
    ('blg', 'baby_luigi'),
    ('ca', 'birdo'),
    ('ds', 'daisy'),
    ('dd', 'diddy_kong'),
    ('ka', 'dry_bones'),
    ('bk', 'dry_bowser'),
    ('fk', 'funky_kong'),
    ('kt', 'king_boo'),
    ('rs', 'rosalina'),
    ('kk', 'toadette'),
    ('jr', 'bowser_jr')
]

from retro_pack import CHARACTER_DIR

def extract_brres_from_szs(szs_path):
    data = Yaz0.decompress(io.BytesIO(szs_path.read_bytes())).getvalue()
    root = struct.unpack_from('>I', data, 4)[0]
    count = struct.unpack_from('>I', data, root + 8)[0]
    strings = root + count * 12
    for i in range(1, count):
        info, offset, size = struct.unpack_from('>III', data, root + i * 12)
        start = strings + (info & 0xffffff)
        name = data[start:data.index(0, start)].decode('latin1')
        if name == 'driver_model.brres':
            return data[offset:offset + size]
    return None

def cook_task(task):
    szs_path, char_name, veh_stem, slot, out_dir = task
    prefix = f"{char_name}_{veh_stem}_skin_{slot}_driver"
    target_gmdl = out_dir / 'models' / f"{prefix}.gmdl"
    target_dskm = out_dir / 'models' / f"{prefix}.dskm"
    if target_gmdl.is_file() and target_dskm.is_file():
        return prefix, True

    try:
        brres_bytes = extract_brres_from_szs(szs_path)
        if not brres_bytes:
            return prefix, False

        tmp_dir = ROOT / f'build/garage-skins/{prefix}'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_brres = tmp_dir / 'driver_model.brres'
        tmp_brres.write_bytes(brres_bytes)

        export_dir = tmp_dir / 'export'
        export_dir.mkdir(parents=True, exist_ok=True)
        cmd = ['node', str(ROOT / 'build/export_brres.mjs'), str(tmp_brres), str(export_dir), 'model', 'drive', '15']
        res = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, 'MKW_RACE_MATERIALS': '1'})
        if res.returncode != 0:
            return prefix, False

        parts = cook(export_dir, out_dir, prefix, preserve_vertices=True)
        if parts:
            cooked_gmdl = out_dir / 'models' / f"{parts[0]['name']}.gmdl"
            if cooked_gmdl.is_file() and cooked_gmdl != target_gmdl:
                shutil.copyfile(cooked_gmdl, target_gmdl)

        cmd_dskm = ['node', str(ROOT / 'build/export_driver.mjs'), str(tmp_brres), str(target_dskm), 'model']
        res_dskm = subprocess.run(cmd_dskm, capture_output=True, text=True,
                                  env={**os.environ, 'MKW_ALLOW_MISSING_FACE_TEXTURES': '1'})
        return prefix, (target_gmdl.is_file() and target_dskm.is_file())
    except Exception as e:
        return prefix, False

def main():
    if not CHARACTER_DIR.is_dir():
        print(f"Character directory not found: {CHARACTER_DIR}")
        raise SystemExit(1)

    out_dir = ROOT / 'sd-card/3ds/mkw-3ds'
    tasks = []

    # Filter to specific driver if requested via CLI arg (e.g. bpc for baby peach)
    target_filter = sys.argv[1] if len(sys.argv) > 1 else None

    for szs_path in sorted(CHARACTER_DIR.glob('*.szs')):
        # Name format: {veh_stem}-{char_stem}-{slot}.szs
        parts = szs_path.stem.split('-')
        if len(parts) != 3:
            continue
        veh_stem, char_stem, slot_str = parts
        try:
            slot = int(slot_str)
        except ValueError:
            continue

        char_name = None
        for stem, name in DRIVERS:
            if stem == char_stem:
                char_name = name
                break
        if not char_name:
            continue

        if target_filter and char_stem != target_filter and char_name != target_filter:
            continue

        prefix = f"{char_name}_{veh_stem}_skin_{slot}_driver"
        target_gmdl = out_dir / 'models' / f"{prefix}.gmdl"
        target_dskm = out_dir / 'models' / f"{prefix}.dskm"
        if not target_gmdl.is_file() or not target_dskm.is_file():
            tasks.append((szs_path, char_name, veh_stem, slot, out_dir))

    print(f"Tasks to cook: {len(tasks)}")
    success = 0
    with ThreadPoolExecutor(max_workers=int(os.environ.get('MKW_SKIN_JOBS', '6'))) as pool:
        for prefix, ok in pool.map(cook_task, tasks):
            if ok:
                success += 1
                print(f"OK {prefix}")
            else:
                print(f"FAIL {prefix}")

    print(f"Finished {success}/{len(tasks)} tasks.")
    if success != len(tasks):raise SystemExit(1)

if __name__ == '__main__':
    main()
