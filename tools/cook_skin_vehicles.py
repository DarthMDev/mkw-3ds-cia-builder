#!/usr/bin/env python3
"""Cook the kart/bike replacements carried by Retro Rewind skin archives."""
import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, struct
from pathlib import Path
from cook_garage_skins import CHARACTER_DIR, DRIVERS, ROOT
from cook_model import cook
from unpack_szs import unpack

OUT = ROOT / 'sd-card/3ds/mkw-3ds'

def run(task):
    archive, row, slot = task
    prefix = f"{row['prefix']}skin_{slot}_"
    work = ROOT / 'build/skin-vehicles' / prefix
    receipt = work / 'receipt.json'
    source_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    if receipt.is_file() and json.loads(receipt.read_text()).get('sourceHash') == source_hash:
        return prefix, True
    try:
        unpack(archive, work / 'source')
        source = work / 'source/kart_model.brres'
        if not source.is_file(): return prefix, True
        if hashlib.sha256(source.read_bytes()).hexdigest() == row['kart_sha256']:
            receipt.write_text(json.dumps({'sourceHash':source_hash,'files':[], 'retailVehicle':True}))
            return prefix, True
        outputs = []; cooked_sources = {}
        for part, model in row['modelSources'].items():
            if part == 'driver': continue
            dest = OUT / 'models' / f'{prefix}{part}.gmdl'
            if model in cooked_sources:
                previous = cooked_sources[model]
                shutil.copyfile(previous,dest);outputs.append(dest.name)
                if previous.with_suffix('.dskm').is_file():
                    shutil.copyfile(previous.with_suffix('.dskm'),dest.with_suffix('.dskm'));outputs.append(dest.with_suffix('.dskm').name)
                continue
            export = work / part
            command = ['node', str(ROOT/'build/export_brres.mjs'), str(source), str(export), model]
            subprocess.run(command, check=True, capture_output=True, env={**os.environ, 'MKW_RACE_MATERIALS':'1'})
            exported=json.loads((export/'model.json').read_text())
            if part not in row['partClips'] and not any(m['shapes'] for m in exported['models']):
                # Some replacements include their wheels in the body and leave
                # separate component models empty. Keep that authored invisibility.
                dest.write_bytes(struct.pack('<4s5I',b'GMDL',3,1,3,0,0)+bytes(44+6))
                outputs.append(dest.name);cooked_sources[model]=dest
                continue
            animated = part in row['partClips']
            models = cook(export, OUT, prefix+part, preserve_vertices=animated)
            if len(models) != 1: raise ValueError(f'{part}: expected one model, got {len(models)}')
            shutil.copyfile(OUT/'models'/f"{models[0]['name']}.gmdl", dest)
            outputs.append(dest.name)
            cooked_sources[model] = dest
            if animated:
                bank = dest.with_suffix('.dskm')
                subprocess.run(['node',str(ROOT/'build/export_driver.mjs'),str(source),str(bank),model],check=True,capture_output=True,
                    env={**os.environ,'MKW_ALLOW_MISSING_FACE_TEXTURES':'1'})
                outputs.append(bank.name)
        receipt.write_text(json.dumps({'sourceHash':source_hash,'files':outputs}))
        return prefix, True
    except Exception as exc:
        (work/'error.txt').write_text(str(exc))
        return prefix, False

if __name__ == '__main__':
    rows = json.loads((ROOT/'build/roster/models/garage.json').read_text())['choices']
    names = dict(DRIVERS); tasks=[]
    for archive in sorted(CHARACTER_DIR.glob('*.szs')):
        parts=archive.stem.split('-')
        if len(parts)!=3 or parts[1] not in names or not parts[2].isdigit(): continue
        vehicle,character,slot=parts
        if len(sys.argv)>1 and character not in sys.argv[1:]:continue
        prefix=f'{names[character]}_{vehicle}_'
        row=next((r for r in rows if r['prefix']==prefix),None)
        if row and (OUT/'models'/f'{prefix}skin_{slot}_driver.gmdl').is_file():tasks.append((archive,row,int(slot)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('MKW_SKIN_JOBS','6'))) as pool:
        good=0
        for prefix,ok in pool.map(run,tasks):
            good+=ok;print('OK' if ok else 'FAIL',prefix,flush=True)
    print(f'{good}/{len(tasks)} skin vehicle archives cooked',flush=True)
