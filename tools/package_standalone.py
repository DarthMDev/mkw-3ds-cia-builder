#!/usr/bin/env python3
"""Embed the current allowlisted private assets into a self-contained 3DSX."""
import argparse, errno, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build';SOURCE=OUT/'playable/3ds/mkw-3ds';STAGE=OUT/'standalone-romfs'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def stage_assets(stage):
    """Link (or copy) every RomFS asset of the staged SD package into stage; return {name: sha256}."""
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    # Cook receipts (JSON) are build records the game never reads: they stay out.
    assets={name:h for name,h in manifest.items() if Path(name).parts[0] in ('Race','models','textures','movies','audio') and not name.endswith('.json')}
    if not assets:raise ValueError('Run tools/package_sd.py first')
    stage.mkdir(exist_ok=True)
    for stale in stage.rglob('*'):
        if stale.is_file() and stale.relative_to(stage).as_posix() not in assets:stale.unlink()
    for name,h in assets.items():
        source=SOURCE/name
        if digest(source)!=h:raise ValueError('Package asset hash mismatch: '+name)
        dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True)
        # Both trees are generated staging on the same volume. Linking avoids
        # duplicating several GiB while producing the standalone container.
        dest.unlink(missing_ok=True)
        try:os.link(source,dest)
        except OSError as error:
            if error.errno not in (errno.EXDEV,errno.EPERM,errno.ENOTSUP,errno.EOPNOTSUPP):raise
            shutil.copyfile(source,dest)
    # Avoid filesystem metadata/resource forks on external macOS volumes.
    for stale in stage.rglob('._*'):
        if stale.is_file():stale.unlink()
    return assets
def package(stage):
    assets=stage_assets(stage)
    from devkitpro import tool, root as devkitpro_root
    dkp=devkitpro_root()
    smdh=OUT/'mkw-3ds.smdh'
    subprocess.run([str(tool('smdhtool')),'--create','MKW/ MARIO KART RECOMPILED 3DS','32 race imports / 10 arena assets','MKW 3DS',str(dkp/'libctru/default_icon.png'),str(smdh)],check=True)
    target=OUT/'mkw-3ds-standalone.3dsx'
    temporary=target.with_suffix('.tmp.3dsx')
    try:
        subprocess.run([str(tool('3dsxtool')),str(OUT/'mkw-3ds.elf'),str(temporary),'--smdh='+str(smdh),'--romfs='+str(stage)],check=True)
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
    receipt={'file':str(target),'sha256':digest(target),'bytes':target.stat().st_size,
             'elf_sha256':digest(OUT/'mkw-3ds.elf'),'assets':assets,'asset_count':len(assets),
             'physical_device_test':False,'manual_test_pending':True}
    (OUT/'standalone-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='assets'},indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temporary-staging',action='store_true',help='Use the system temporary volume for RomFS staging when the project volume is nearly full.')
    args=parser.parse_args()
    if args.temporary_staging:
        with tempfile.TemporaryDirectory(prefix='mkw-romfs-') as directory:package(Path(directory))
    else:package(STAGE)

if __name__=='__main__':main()
