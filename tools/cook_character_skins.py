#!/usr/bin/env python3
"""Cook Retro Rewind character skins into 3DS GMDL/DSKM menu models and textures."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cook_model import cook
from retro_pack import CHARACTER_DIR

DRIVERS = [
    'mr',        # 0: Mario -> mr-X.brres
    'lg',        # 1: Luigi -> lg-X.brres
    'pc',        # 2: Peach -> pc-X.brres
    'ys',        # 3: Yoshi -> ys-X.brres
    'bmr',       # 4: Baby Mario -> bmr-X.brres
    'bpc',       # 5: Baby Peach -> bpc-X.brres
    'ko',        # 6: Toad -> ko-X.brres
    'nk',        # 7: Koopa Troopa -> nk-X.brres
    'wr',        # 8: Wario -> wr-X.brres
    'wl',        # 9: Waluigi -> wl-X.brres
    'dk',        # 10: Donkey Kong -> dk-X.brres
    'kp',        # 11: Bowser -> kp-X.brres
    'bds',       # 12: Baby Daisy -> bds-X.brres
    'blg',       # 13: Baby Luigi -> blg-X.brres
    'ca',        # 14: Birdo -> ca-X.brres
    'ds',        # 15: Daisy -> ds-X.brres
    'dd',        # 16: Diddy Kong -> dd-X.brres
    'ka',        # 17: Dry Bones -> ka-X.brres
    'bk',        # 18: Dry Bowser -> bk-X.brres
    'fk',        # 19: Funky Kong -> fk-X.brres
    'kt',        # 20: Toadette -> kt-X.brres
    'rs',        # 21: Rosalina -> rs-X.brres
    'kk',        # 22: King Boo -> kk-X.brres
    'jr'         # 23: Bowser Jr. -> jr-X.brres
]

def cook_skin(args):
    drv_idx, stem, slot, source, out_dir = args
    prefix = f'ui_driver_{drv_idx}_skin_{slot}'
    export = ROOT / f'build/menu-models/{prefix}'
    export.mkdir(parents=True, exist_ok=True)

    target_gmdl = out_dir / 'models' / f'{prefix}_000.gmdl'
    target_dskm = out_dir / 'models' / f'{prefix}.dskm'
    if target_gmdl.is_file() and target_dskm.is_file():
        return prefix, True

    try:
        res = subprocess.run(
            ['node', str(ROOT / 'build/export_brres.mjs'), str(source), str(export), 'model', 'sel_wait', '0'],
            capture_output=True, text=True, env={**os.environ, 'MKW_MENU_MATERIALS': '1'}
        )
        if res.returncode != 0:
            print(f'Failed export_brres for {prefix}: {res.stderr[:200]}')
            return prefix, False

        cook(export, out_dir, prefix, max_texture=256, preserve_vertices=True)

        res = subprocess.run(
            ['node', str(ROOT / 'build/export_driver.mjs'), str(source), str(target_dskm), 'model'],
            capture_output=True, text=True
        )
        if res.returncode != 0:
            print(f'Failed export_driver for {prefix}: {res.stderr[:200]}')
            return prefix, False

        return prefix, True
    except Exception as e:
        print(f'Error processing {prefix}: {e}')
        return prefix, False

def main():
    driver_dir = CHARACTER_DIR / 'Driver'
    if not driver_dir.is_dir():
        print(f'Directory not found: {driver_dir}')
        raise SystemExit(1)

    out_dirs = [
        ROOT / 'sd-card/3ds/mkw-3ds'
    ]

    tasks = []
    for drv_idx, stem in enumerate(DRIVERS):
        for slot in range(1, 10):
            source = driver_dir / f'{stem}-{slot}.brres'
            if source.is_file():
                for out_dir in out_dirs:
                    tasks.append((drv_idx, stem, slot, source, out_dir))

    print(f'Found {len(tasks)} distinct driver skins to process.')

    success = 0
    with ThreadPoolExecutor(max_workers=int(os.environ.get('MKW_SKIN_JOBS', '4'))) as pool:
        for prefix, ok in pool.map(cook_skin, tasks):
            if ok:
                success += 1

    print(f'Done! Successfully processed {success}/{len(tasks)} targets.')
    if success != len(tasks):raise SystemExit(1)

if __name__ == '__main__':
    main()
