#!/usr/bin/env python3
"""Cook the authored AllKart menu previews for custom skins."""
import concurrent.futures, json, os, subprocess
from pathlib import Path
from cook_garage_skins import CHARACTER_DIR, ROOT
from cook_menu_models import DRIVERS, MACHINES, WEIGHTS
from cook_model import cook
from unpack_szs import unpack
OUT=ROOT/'sd-card/3ds/mkw-3ds'

def run(task):
    archive,driver,slot=task
    work=ROOT/'build/skin-menu-vehicles'/archive.stem
    try:
        unpack(archive,work/'source')
        for choice,stem in enumerate(MACHINES):
            source=work/'source'/f'{"sml"[WEIGHTS[driver]]}{stem}.brres'
            if not source.is_file():continue
            prefix=f'ui_machine_{driver}_{choice}_skin_{slot}'
            if (OUT/'models'/f'{prefix}_000.gmdl').is_file():continue
            export=work/str(choice)
            subprocess.run(['node',str(ROOT/'build/export_brres.mjs'),str(source),str(export),'menu'],check=True,capture_output=True,env={**os.environ,'MKW_MENU_MATERIALS':'1'})
            parts=cook(export,OUT,prefix,max_texture=256)
            if len(parts)!=1:raise ValueError('menu preview must fit one model')
        return archive.name,True
    except Exception as e:return archive.name,str(e)
if __name__=='__main__':
    tasks=[]
    for p in sorted((CHARACTER_DIR/'AllKart').glob('*.szs')):
        parts=p.stem.split('-')
        if len(parts)!=3 or not parts[1].isdigit():continue
        code,slot,_=parts
        if code in [d.removesuffix('_menu') for d in DRIVERS]:tasks.append((p,[d.removesuffix('_menu') for d in DRIVERS].index(code),int(slot)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('MKW_SKIN_JOBS','6'))) as pool:
        failed=False
        for name,ok in pool.map(run,tasks):
            print(name,ok,flush=True)
            if ok is not True:failed=True
    if failed:raise SystemExit(1)
