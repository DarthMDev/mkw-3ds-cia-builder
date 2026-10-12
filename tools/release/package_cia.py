#!/usr/bin/env python3
"""Package the all-in-one CIA: the program plus every cooked asset in RomFS.

Needs build/mkw-3ds.elf and the staged SD package (tools/package_sd.py
--no-zip). The RomFS is staged with hard links beside that package (same
volume, no copy), the HOME Menu art is made from the player's own disc
(home_menu_art.py), and makerom builds the CIA. --cci builds a cartridge
image of the same content instead, which emulators boot without installing.
"""
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(Path(__file__).parent)]
from package_standalone import SOURCE, stage_assets, digest
from bootstrap_tools import tools
import home_menu_art
RSF=Path(__file__).with_name('mkw-3ds.rsf')
TITLE='Mario Kart Wii 3DS'  # HOME Menu name
UNIQUE_ID=0xF4B57
TITLE_ID=0x0004000000000000|UNIQUE_ID<<8
# Quick updates install as this title's update (Patch), like a retail game
# update: the system runs the update's code and keeps the application's icon,
# banner and sound, which were made from the player's disc.
UPDATE_TITLE_ID=0x0004000E00000000|UNIQUE_ID<<8

def version_number(text):
    major,minor,micro=(int(v) for v in text.split('.'))
    if not(0<=major<64 and 0<=minor<64 and 0<=micro<16):raise SystemExit('version must be major.minor.micro within 63.63.15')
    return major<<10|minor<<4|micro

def run(*args):
    subprocess.run([str(a) for a in args],check=True)

def package(cci=False,version='0.1.0',output=None,update=False):
    # update: the code-only Patch CIA. Its game files come from the SD card
    # (written by the builder) or the application's own RomFS when that matches;
    # its own HOME Menu art is drawn without the disc and is not what is shown.
    elf=ROOT/'build/mkw-3ds.elf'
    if not elf.is_file():raise SystemExit('Build the program first (tools/build.py)')
    if not update and not (SOURCE/'manifest.json').is_file():raise SystemExit('Stage the package first (tools/package_sd.py --no-zip)')
    makerom,bannertool=tools()
    out=ROOT/'build/release';art=out/'art';out.mkdir(parents=True,exist_ok=True)
    if update:art=out/'art-update';icon,banner,sound=home_menu_art.generic(art)
    else:icon,banner,sound=home_menu_art.make(art,SOURCE/'movies/title_bgm.wav')
    run(bannertool,'makebanner','-i',banner,'-a',sound,'-o',art/'banner.bnr')
    run(bannertool,'makesmdh','-s',TITLE,'-l',TITLE+' (unofficial port)','-p','mkw-3ds',
        '-i',icon,'-o',art/'icon.icn','-r','regionfree','-f','visible,allow3d,recordusage')
    target=output or out/('mkw-3ds-update.cia' if update else 'mkw-3ds.cci' if cci else 'mkw-3ds.cia')
    temporary=target.with_name(target.name+'.tmp')
    # Beside the staged package, so hard links work wherever the player builds.
    with tempfile.TemporaryDirectory(prefix='mkw-cia-romfs-',dir=(ROOT/'build') if update else SOURCE.resolve().parents[2]) as stage:
        if update:
            (Path(stage)/'update.txt').write_text('Game files are read from sdmc:/3ds/mkw-3ds (made by the builder).\n');assets={}
        else:
            assets=stage_assets(Path(stage))
            # Which converted game files these are, as on the SD card: updated
            # code uses this RomFS only when it expects the same content.
            from build_cia import content_fingerprint
            (Path(stage)/'content.txt').write_text(content_fingerprint()+'\n')
        try:
            run(makerom,'-f','cci' if cci else 'cia','-target','t','-exefslogo','-elf',elf,'-rsf',RSF,
                '-icon',art/'icon.icn','-banner',art/'banner.bnr','-ver',version_number(version),
                f'-DAPP_ROMFS={stage}','-DAPP_CATEGORY='+('Patch' if update else 'Application'),'-DAPP_REMASTER=0','-o',temporary)
            temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
    receipt={'file':str(target),'format':'cci' if cci else 'cia','sha256':digest(target),'bytes':target.stat().st_size,
             'title_id':f'{UPDATE_TITLE_ID if update else TITLE_ID:016X}','version':version,'elf_sha256':digest(elf),'asset_count':len(assets),
             'assets_sha256':hashlib.sha256(json.dumps(assets,sort_keys=True).encode()).hexdigest(),
             'tools':json.loads((makerom.parent/'tools-verified.json').read_text())}
    target.with_name(target.name+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    return target

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cci',action='store_true',help='cartridge image for emulator boot tests instead of a CIA')
    # The HOME Menu refreshes a title's cached icon and banner only when its
    # version rises: bump tools/release/VERSION for every build you share.
    p.add_argument('--version',default=(Path(__file__).parent/'VERSION').read_text().strip())
    p.add_argument('--output',type=Path)
    p.add_argument('--update',action='store_true',help='code-only update CIA (Patch title): game files from the SD card, no disc needed')
    a=p.parse_args()
    package(a.cci,a.version,a.output,a.update)
