#!/usr/bin/env python3
"""Mario Kart Wii 3DS: build the all-in-one CIA from your own disc.

    python tools/release/build_cia.py "Mario Kart Wii (USA).iso"

Stages, each skipped when its outputs already exist (rerun to resume):
  tools    pinned makerom and bannertool; devkitPro, Python packages, Node
  sources  pinned Kinoko, noclip, gclib and citro3d with this tree's patches
  disc     USA Mario Kart Wii (RMCE01) ISO or WBFS; extracted files must match
           tools/release/usa-disc.json
  cook     every asset, from the disc, in dependency order (COOK_STEPS)
  compile  tools/build.py
  package  tools/package_sd.py --no-zip, then the CIA (package_cia.py)

Only pinned public tools and sources are downloaded. The disc and everything
made from it stay on this machine; nothing from it is in this repository.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(HERE)]
SD='sd-card/3ds/mkw-3ds'
DISC_MANIFEST=json.loads((HERE/'usa-disc.json').read_text())
MENU_ARCHIVES=['MenuSingle','MenuSingle_U','MenuOther','MenuOther_U','Title','Title_U','Award','Award_U','Globe']
COURSE_OVERLAY_IDS=['1','5','7','8','10','15','19','27','29','31']

# (name, command, outputs that mean the step is done). {py} is this Python,
# {disc} the disc image, {jobs} the worker count. Order is dependency order.
# Intermediates no later step reads, deleted (fresh trees only) once the
# named step succeeds: several GB the player's disk never needs at once.
PRUNE_AFTER={'course material overlay':['build/course-exports','build/object-exports'],
             'full roster':['assets/garage-parts']}

COOK_STEPS=[
 ('Node packages',['npm','ci','--no-audit','--no-fund'],['node_modules/.package-lock.json']),
 ('BRRES exporters',['node','tools/bundle_cooker.mjs'],['build/export_brres.mjs']),
 # The game module, read as data (menu palettes, layouts, animation tables).
 ('game module',['{py}','tools/extract_disc.py','{disc}','data/extracted','--file','rel/StaticR.rel','--to','build/itembox-retail.rel'],['build/itembox-retail.rel']),
 ('menus, movies and sound',['{py}','tools/extract_disc.py','{disc}','data/extracted','--prefix','Scene/','--prefix','thp/','--prefix','sound/','--prefix','Boot/'],['data/extracted/Scene/UI/Title.szs','data/extracted/sound/revo_kart.brsar','data/extracted/thp/title','data/extracted/Boot/Strap/us/English.szs']),
 # Coconut Mall's sky predates the course importer, which reuses it (README.txt).
 ('Coconut Mall archive',['{py}','tools/unpack_szs.py','data/extracted/Race/Course/shopping_course.szs','assets/coconut-mall'],['assets/coconut-mall/vrcorn_model.brres']),
 ('Coconut Mall sky export',['node','build/export_brres.mjs','assets/coconut-mall/vrcorn_model.brres','assets/cooked-coconut-sky'],['assets/cooked-coconut-sky/model.json']),
 ('Coconut Mall sky',['{py}','tools/cook_model.py','assets/cooked-coconut-sky',SD,'--prefix','coconut_sky'],[SD+'/models/coconut_sky.list']),
 ('race courses and arenas',['{py}','tools/import_courses.py','--jobs','{jobs}'],[SD+'/models/course-catalog.json']),
 ('course objects',['{py}','tools/cook_course_objects.py','--jobs','{jobs}'],[SD+'/models/course_08_visuals.list']),
 ('Coconut Mall escalators and palms',['{py}','tools/cook_coconut_objects.py'],[SD+'/models/coconut_escalator_000.gmdl',SD+'/models/coconut_palm_000.gmdl']),
 ('course lighting',['{py}','tools/lighting/recook_courses.py','--jobs','{jobs}','--no-pack'],[]),
 ('course material overlay',['{py}','tools/cook_course_overlay.py','--ids',*COURSE_OVERLAY_IDS,'--objects'],['build/course-materials/models']),
 ('drivers',['{py}','tools/cook_roster.py','{disc}',SD],[SD+'/models/roster.json']),
 ('karts and bikes',['{py}','tools/cook_garage.py','{disc}',SD],[SD+'/models/garage.json']),
 ('full roster',['{py}','tools/cook_full_roster.py','--jobs','{jobs}'],['build/roster']),
 ('kart effects',['{py}','tools/cook_effects.py','assets/common/Effect/RKRace.breft',SD+'/textures'],[SD+'/textures/drift-effects.bin']),
 ('bike effects',['{py}','tools/cook_effects.py','assets/common/Effect/RKRace.breft',SD+'/textures','--bike'],[SD+'/textures/drift-effects-bike.bin']),
 # The item box model comes from Luigi Circuit's archive, unpacked where the item cook expects it.
 ('Luigi Circuit archive',['{py}','tools/unpack_szs.py','data/extracted/Race/Course/beginner_course.szs','assets/luigi'],['assets/luigi/itembox.brres']),
 ('items and HUD',['{py}','tools/cook_race_items.py',SD,'--disc','{disc}'],[SD+'/models/race-items.json']),
 ('race effects',['{py}','tools/cook_race_effects.py','--output','build/vfx/textures'],['build/vfx/textures/race-effects.bin']),
 ('blast effects',['{py}','tools/cook_blast.py'],['build/vfx/models/bomb_blast.gmdl']),
 ('Lakitu',['{py}','tools/cook_lakitu.py'],['build/vfx/models/lakitu_body.dskm']),
 ('name balloons',['{py}','tools/cook_race_balloon.py'],['build/vfx/textures/hud_balloon_line.t3x']),
 ('race flow and results',['{py}','tools/cook_race_flow.py'],['build/race-flow/textures/flow_wipe.t3x']),
 ('audio',['{py}','tools/cook_audio.py'],['build/audio/audio/manifest.json']),
 # Menu layouts and models, unpacked where the menu cooks read them.
 ('menu archives',[['{py}','tools/unpack_szs.py',f'data/extracted/Scene/UI/{a}.szs',f'assets/menu-ui/{a}'] for a in MENU_ARCHIVES],
  ['assets/menu-ui/Title/title/timg/tt_title_screen_mario2.tpl']),
 ('menu model archives',[['{py}','tools/unpack_szs.py',f'data/extracted/Scene/Model/{a}.szs',f'assets/menu-models/{a}'] for a in ('Driver','BackModel')],
  ['assets/menu-models/Driver','assets/menu-models/BackModel']),
 ('menu interface',['{py}','tools/cook_menu_ui.py'],[SD+'/models/menu-ui.json']),
 ('menu models',['{py}','tools/cook_menu_models.py','--machines','--jobs','{jobs}'],[SD+'/models/menu-models.json']),
 ('menu movies',['{py}','tools/cook_menu_movies.py','--jobs','{jobs}'],[SD+'/models/menu-movies.json',SD+'/movies/title.wav']),
 ('menu audio',['{py}','tools/cook_menu_audio.py'],[SD+'/models/menu-audio.json']),
 ('race bottom screen',['{py}','tools/cook_race_map.py','--jobs','{jobs}'],['build/race-map/textures/race_bottom_ui.t3x']),
 # The SD build's archives index the finished package, so they come last.
 ('menu archive',['{py}','tools/pack_menu_assets.py'],[SD+'/menu.pak']),
 ('race archive',['{py}','tools/pack_race_assets.py'],[SD+'/race.pak']),
]

def log(*a):print('[build_cia]',*a,flush=True)

def run(cmd,**kw):
    log('$',' '.join(str(c) for c in cmd))
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(p for p in (str(ROOT/'vendor/gclib'),os.environ.get('PYTHONPATH')) if p))
    subprocess.run([str(c) for c in cmd],cwd=ROOT,check=True,env=env,**kw)

def shared_checkout():
    """Development trees link data/, assets/ and sd-card/ to a shared checkout."""
    return [d for d in ('data','assets','sd-card') if (ROOT/d).is_symlink()]

def stage_tools():
    from bootstrap_tools import tools
    makerom,bannertool=tools();log('makerom',makerom);log('bannertool',bannertool)
    dkp=Path(os.environ.get('DEVKITPRO','/opt/devkitpro'))
    for need in (dkp/'devkitARM',dkp/'libctru',dkp/'tools/bin'/('tex3ds'+('.exe' if os.name=='nt' else ''))):
        if not need.exists():raise SystemExit(f'Missing {need}: install devkitPro 3ds-dev (https://devkitpro.org/wiki/Getting_Started)')
    missing=[m for m in ('numpy','PIL','Crypto') if not __import__('importlib.util').util.find_spec(m)]
    if missing:raise SystemExit('Missing Python packages '+', '.join(missing)+': pip install -r requirements.txt')
    if not shutil.which('node'):raise SystemExit('Missing Node.js (https://nodejs.org), used by the model exporters')

def stage_sources():
    if all((ROOT/'vendor'/n).is_dir() for n in ('kinoko','noclip','gclib','citro3d')):log('sources present');return
    run([sys.executable,'tools/bootstrap.py'])

def stage_disc(disc):
    receipt=ROOT/'data/extracted/extraction-receipt.json'
    if not receipt.is_file():
        if not disc:raise SystemExit('Give the path to your Mario Kart Wii (USA) ISO or WBFS')
        run([sys.executable,'tools/extract_disc.py',disc,'data/extracted'])
    r=json.loads(receipt.read_text());ident=DISC_MANIFEST['identity']
    if any(r['identity'][k]!=v for k,v in ident.items()):
        raise SystemExit(f"Unsupported disc {r['identity']['game_id']} revision {r['identity']['revision']}: only Mario Kart Wii USA (RMCE01) is supported")
    got={f['name']:f['sha256'] for f in r['files']}
    bad=[n for n,h in DISC_MANIFEST['files'].items() if got.get(n)!=h]
    if bad:raise SystemExit(f'{len(bad)} extracted files differ from an unmodified USA disc (first: {bad[0]}). Use a clean dump.')
    log(f"disc verified: {ident['game_id']} revision {ident['revision']}, {len(got)} files")

def scrub_appledouble():
    """Delete macOS '._' metadata files from the cooked trees. macOS writes
    one beside every file on volumes without extended attributes (exFAT, FAT),
    and the cookers' globs ('*.brlan', '*.brctr' ...) would read them as data."""
    if sys.platform!='darwin':return
    for top in ('data','assets','sd-card','build'):
        for dirpath,dirnames,filenames in os.walk(ROOT/top):
            for f in filenames:
                if f.startswith('._'):Path(dirpath,f).unlink(missing_ok=True)

def stage_cook(disc,jobs,force,check=False):
    shared=shared_checkout();stamps=ROOT/'build/release/cook';stamps.mkdir(parents=True,exist_ok=True)
    rerun=force
    for name,cmd,outputs in COOK_STEPS:
        stamp=stamps/(name.replace(' ','-')+'.done')
        present=bool(outputs) and all((ROOT/o).exists() for o in outputs)
        # A fresh tree trusts only success stamps (a failed step can leave its
        # outputs half written) and, once a step runs, re-runs every later step.
        # Development trees, cooked by hand, are judged by their outputs; so are
        # the Node packages, which a development tree links from elsewhere.
        done=(present if shared or name=='Node packages' else stamp.is_file()) and not rerun
        if done:log('cooked:',name);continue
        # The course lighting re-cook rewrites files in place: no output of its own.
        if shared and not outputs:log('cooked (development tree, assumed):',name);continue
        if check:raise SystemExit(f"Cook step '{name}' has not run")
        if shared:raise SystemExit(f"Cook step '{name}' is missing, but {', '.join(shared)} link to a shared checkout. Build from a fresh clone.")
        rerun=True
        commands=cmd if cmd and isinstance(cmd[0],list) else [cmd]
        if any('{disc}' in c for c in commands) and not disc:raise SystemExit(f"Cook step '{name}' needs the disc image path")
        start=time.monotonic()
        for c in commands:
            scrub_appledouble();run([str(a).replace('{py}',sys.executable).replace('{disc}',str(disc)).replace('{jobs}',str(jobs)) for a in c])
        stamp.write_text(f'{time.monotonic()-start:.0f} s\n')
        for path in PRUNE_AFTER.get(name,()):shutil.rmtree(ROOT/path,ignore_errors=True)

def stage_compile(jobs):
    run([sys.executable,'tools/build.py','--jobs',str(jobs),'--release'])

def stage_package(version,cci,keep_stage):
    run([sys.executable,'tools/package_sd.py','--no-zip'])
    import package_cia
    try:return package_cia.package(cci,version)
    finally:
        if not keep_stage:shutil.rmtree(ROOT/'build/playable',ignore_errors=True)

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('disc',nargs='?',type=Path,help='your Mario Kart Wii (USA) ISO or WBFS (not needed once extracted and cooked)')
    p.add_argument('--version',default='0.1.0')
    p.add_argument('--jobs',type=int,default=max(1,(os.cpu_count() or 2)-1))
    p.add_argument('--cci',action='store_true',help='also build a cartridge image for emulators')
    p.add_argument('--force-cook',action='store_true',help='re-run every cook step')
    p.add_argument('--skip-compile',action='store_true',help='package the existing build/mkw-3ds.elf')
    p.add_argument('--keep-stage',action='store_true',help='keep build/playable after packaging')
    p.add_argument('--check',action='store_true',help='verify tools, disc and cooked assets, then stop')
    p.add_argument('--cook-only',action='store_true',help='stop after cooking')
    a=p.parse_args()
    stage_tools();stage_sources();stage_disc(a.disc);stage_cook(a.disc,a.jobs,a.force_cook,a.check)
    if a.check:log('check passed: ready to compile and package');return
    if a.cook_only:log('cook complete');return
    if not a.skip_compile:stage_compile(a.jobs)
    cia=stage_package(a.version,False,a.keep_stage or a.cci)
    if a.cci:stage_package(a.version,True,a.keep_stage)
    log('done:',cia)
    log('Copy it to your SD card and install it with FBI, or use FBI remote install.')

if __name__=='__main__':main()
