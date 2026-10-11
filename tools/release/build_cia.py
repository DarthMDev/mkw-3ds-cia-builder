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
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
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
 ('Node packages',['npm.cmd' if os.name=='nt' else 'npm','ci','--no-audit','--no-fund'],['node_modules/.package-lock.json']),
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
    # PYTHONUTF8: text files are UTF-8 on every OS (Windows would default to cp1252).
    env=dict(os.environ,PYTHONUTF8='1',PYTHONPATH=os.pathsep.join(p for p in (str(ROOT/'vendor/gclib'),os.environ.get('PYTHONPATH')) if p))
    subprocess.run([str(c) for c in cmd],cwd=ROOT,check=True,env=env,**kw)

def shared_checkout():
    """Development trees link data/, assets/ and sd-card/ to a shared checkout."""
    return [d for d in ('data','assets','sd-card') if (ROOT/d).is_symlink()]

def stage_tools():
    from bootstrap_tools import tools
    makerom,bannertool=tools();log('makerom',makerom);log('bannertool',bannertool)
    from devkitpro import tool, root as devkitpro_root
    dkp=devkitpro_root()
    for need in (dkp/'devkitARM',dkp/'libctru',tool('tex3ds')):
        if not need.exists():raise SystemExit(f'Missing {need}: install devkitPro 3ds-dev (https://devkitpro.org/wiki/Getting_Started)')
    missing=[m for m in ('numpy','PIL','Crypto') if not __import__('importlib.util').util.find_spec(m)]
    if missing:raise SystemExit('Missing Python packages '+', '.join(missing)+': pip install -r requirements.txt')
    if not shutil.which('node'):raise SystemExit('Missing Node.js (https://nodejs.org), used by the model exporters')

def stage_sources():
    if all((ROOT/'vendor'/n).is_dir() for n in ('kinoko','noclip','gclib','citro3d')):log('sources present');return
    run([sys.executable,'tools/bootstrap.py'])

def stage_disc(disc):
    if disc and not Path(disc).is_file():raise SystemExit(f'No disc image at: {disc}')
    receipt=ROOT/'data/extracted/extraction-receipt.json'
    # An extraction that failed the check (a Europe disc, a modified or NKit
    # dump) is replaced when a different image is given, e.g. the USA ISO.
    # A verified one is kept: later steps read it even if the ISO has moved.
    if disc and receipt.is_file():
        old=json.loads(receipt.read_text())
        got={f['name']:f['sha256'] for f in old.get('files',[])}
        verified=all(old['identity'].get(k)==v for k,v in DISC_MANIFEST['identity'].items()) and all(got.get(n)==h for n,h in DISC_MANIFEST['files'].items())
        if not verified and (old['identity'].get('source')!=str(disc) or old['identity'].get('source_bytes')!=Path(disc).stat().st_size):
            log('replacing the previous, unsupported disc extraction')
            shutil.rmtree(ROOT/'data/extracted')
    if not receipt.is_file():
        if not disc:raise SystemExit('Give the path to your Mario Kart Wii (USA) ISO or WBFS')
        # NKit images mark themselves "NKIT" at 0x200; their trimmed data fails the checks.
        with open(disc,'rb') as f:f.seek(0x200);nkit=f.read(4)==b'NKIT'
        if nkit:raise SystemExit('This is an NKit image. Convert it to a normal ISO in Dolphin first (right-click the game, Convert File, ISO).')
        log('unpacking and checking your disc: this takes a few minutes with no output')
        run([sys.executable,'tools/extract_disc.py',disc,'data/extracted'])
    r=json.loads(receipt.read_text());ident=DISC_MANIFEST['identity']
    if any(r['identity'][k]!=v for k,v in ident.items()):
        game=r['identity']['game_id'];region={'RMCP01':'Europe (PAL)','RMCJ01':'Japan','RMCK01':'Korea'}.get(game)
        what=f"Mario Kart Wii {region} ({game})" if region else f"disc {game} revision {r['identity']['revision']}"
        raise SystemExit(f"This is {what}. Only the USA version of Mario Kart Wii (RMCE01) works for now.")
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

# ---- Step fingerprints --------------------------------------------------------
# A step's done-stamp records a fingerprint of the code that produced it: the
# tool scripts it runs, the local modules they import, and the BRRES exporter
# sources when they call them. An update that changes that code re-runs the
# step (and, as before, every step after it). Line endings are normalised so a
# Windows checkout fingerprints the same as macOS.
_IMPORT=re.compile(r'^\s*(?:from\s+([A-Za-z_]\w*)\s+import|import\s+([A-Za-z_][\w, ]*))',re.M)
_TOOL_DIRS=('tools','tools/release','tools/lighting')
def _local_module(name):
    for d in _TOOL_DIRS:
        f=ROOT/d/(name+'.py')
        if f.is_file():return f
    return None
def step_fingerprint(cmd):
    commands=cmd if cmd and isinstance(cmd[0],list) else [cmd]
    # Only checked-in sources count: build/export_*.mjs are generated bundles
    # (machine-specific), represented by the tools/*.ts they are built from.
    files=set();queue=[ROOT/a for c in commands for a in c if isinstance(a,str) and a.startswith('tools/') and a.endswith(('.py','.mjs')) and (ROOT/a).is_file()]
    exporters=any('build/export_' in a or 'bundle_cooker' in a for c in commands for a in c if isinstance(a,str))
    if any(a.startswith('npm') for c in commands for a in c if isinstance(a,str)):queue.append(ROOT/'package-lock.json')
    while queue:
        f=queue.pop()
        if f in files:continue
        files.add(f)
        if f.suffix!='.py':continue
        text=f.read_text(encoding='utf-8',errors='replace')
        exporters|='.mjs' in text
        for a,b in _IMPORT.findall(text):
            for name in ([a] if a else [n.strip().split(' ')[0] for n in b.split(',')]):
                m=_local_module(name)
                if m:queue.append(m)
    if exporters:files|={*(ROOT/'tools').glob('*.ts'),ROOT/'tools/bundle_cooker.mjs'}
    digest=hashlib.sha256(json.dumps(commands).encode())
    for f in sorted(files,key=lambda f:f.relative_to(ROOT).as_posix()):
        digest.update(f.relative_to(ROOT).as_posix().encode()+b'\0'+f.read_bytes().replace(b'\r\n',b'\n'))
    return digest.hexdigest()

# Stamps from builders before fingerprints only say the step finished. Trust
# them, except where a later version changed what the step makes.
def _legacy_stamp_ok(name):
    def json_at(rel):
        try:return json.loads((ROOT/rel).read_text())
        except (OSError,ValueError):return None
    if name=='karts and bikes':  # all twelve vehicles per driver
        g=json_at(SD+'/models/garage.json');return bool(g)and len(g.get('choices',[]))==288
    if name=='race effects':     # smoke and dust emitters
        e=json_at('build/vfx/textures/race-effects.json');return bool(e)and 'rk_start0' in e.get('emitters',[])
    if name=='drivers':          # Toadette's braids (her hair model's vertices)
        d=ROOT/SD/'models/toadette_driver.dskm'
        try:return d.is_file() and int.from_bytes(d.read_bytes()[8:12],'little')>1716
        except OSError:return False
    return True

# The content stamp: every conversion step's fingerprint plus the packaging
# scripts that lay out the SD folder. The update CIA is compiled with it
# (tools/build.py -> MKW_CONTENT) and the builder writes it to the SD folder
# (content.txt), so code and game files from different builders don't mix.
PACKAGE_SCRIPTS=('tools/package_sd.py','tools/package_standalone.py')
def content_fingerprint():
    digest=hashlib.sha256()
    for name,cmd,_ in COOK_STEPS:digest.update(f'{name}\0{step_fingerprint(cmd)}\n'.encode())
    for script in PACKAGE_SCRIPTS:digest.update((ROOT/script).read_bytes().replace(b'\r\n',b'\n'))
    return digest.hexdigest()[:32]

def stamp_done(stamp,name,fingerprint):
    if not stamp.is_file():return False
    text=stamp.read_text().strip()
    if text.startswith('fingerprint '):return text.split()[1]==fingerprint
    return _legacy_stamp_ok(name)

def stage_cook(disc,jobs,force,check=False):
    shared=shared_checkout();stamps=ROOT/'build/release/cook';stamps.mkdir(parents=True,exist_ok=True)
    rerun=force
    for name,cmd,outputs in COOK_STEPS:
        stamp=stamps/(name.replace(' ','-')+'.done');fingerprint=step_fingerprint(cmd)
        present=bool(outputs) and all((ROOT/o).exists() for o in outputs)
        # A fresh tree trusts only success stamps (a failed step can leave its
        # outputs half written) and, once a step runs, re-runs every later step.
        # Development trees, cooked by hand, are judged by their outputs; so are
        # the Node packages, which a development tree links from elsewhere.
        done=(present if shared or name=='Node packages' else stamp_done(stamp,name,fingerprint)) and not rerun
        if done:log('cooked:',name);continue
        # The course lighting re-cook rewrites files in place: no output of its own.
        if shared and not outputs:log('cooked (development tree, assumed):',name);continue
        if check:raise SystemExit(f"Cook step '{name}' has not run")
        if shared:raise SystemExit(f"Cook step '{name}' is missing, but {', '.join(shared)} link to a shared checkout. Build from a fresh clone.")
        rerun=True
        commands=cmd if cmd and isinstance(cmd[0],list) else [cmd]
        if any('{disc}' in c for c in commands) and not disc:raise SystemExit(f"Cook step '{name}' needs the disc image path")
        start=time.monotonic()
        log(f'step {[n for n,*_ in COOK_STEPS].index(name)+1}/{len(COOK_STEPS)}: {name}')
        for c in commands:
            scrub_appledouble();run([str(a).replace('{py}',sys.executable).replace('{disc}',str(disc)).replace('{jobs}',str(jobs)) for a in c])
        stamp.write_text(f'fingerprint {fingerprint}\n{time.monotonic()-start:.0f} s\n')
        for path in PRUNE_AFTER.get(name,()):shutil.rmtree(ROOT/path,ignore_errors=True)

def stage_compile(jobs):
    run([sys.executable,'tools/build.py','--jobs',str(jobs),'--release'])

SD_OUTPUT=ROOT/'build/release/sd-card'

def stage_package(version,cci,keep_stage):
    run([sys.executable,'tools/package_sd.py','--no-zip'])
    import package_cia
    target=package_cia.package(cci,version)
    # The staged files become the SD card copy for the update CIA:
    # build/release/sd-card/3ds/mkw-3ds plus its content stamp.
    if not cci:
        shutil.rmtree(SD_OUTPUT,ignore_errors=True)
        if keep_stage:shutil.copytree(ROOT/'build/playable',SD_OUTPUT)
        else:shutil.move(str(ROOT/'build/playable'),str(SD_OUTPUT))
        (SD_OUTPUT/'3ds/mkw-3ds/content.txt').write_text(content_fingerprint()+'\n')
        log('SD card files for update CIAs:',SD_OUTPUT/'3ds')
    elif not keep_stage:shutil.rmtree(ROOT/'build/playable',ignore_errors=True)
    return target

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('disc',nargs='?',type=Path,help='your Mario Kart Wii (USA) ISO or WBFS (not needed once extracted and cooked)')
    # The HOME Menu refreshes a title's cached icon and banner only when its
    # version rises: bump tools/release/VERSION for every build you share.
    p.add_argument('--version',default=(Path(__file__).parent/'VERSION').read_text().strip())
    p.add_argument('--jobs',type=int,default=max(1,(os.cpu_count() or 2)-1))
    p.add_argument('--cci',action='store_true',help='also build a cartridge image for emulators')
    p.add_argument('--force-cook',action='store_true',help='re-run every cook step')
    p.add_argument('--skip-compile',action='store_true',help='package the existing build/mkw-3ds.elf')
    p.add_argument('--keep-stage',action='store_true',help='keep build/playable after packaging')
    p.add_argument('--check',action='store_true',help='verify tools, disc and cooked assets, then stop')
    p.add_argument('--cook-only',action='store_true',help='stop after cooking')
    p.add_argument('--pack',type=Path,help='path to a Pulsar / Retro Rewind mod pack directory')
    p.add_argument('--pack-config',type=str,default=None,help='specific Config.pul file in pack (e.g. ConfigRT.pul)')
    p.add_argument('--max-cups',type=int,default=None,help='limit number of mod cups to import')
    a=p.parse_args()
    stage_tools();stage_sources();stage_disc(a.disc);stage_cook(a.disc,a.jobs,a.force_cook,a.check)
    if a.pack:
        log('ingesting Pulsar mod pack:',a.pack)
        cmd=[sys.executable,'tools/import_pulsar_pack.py',a.pack,'--jobs',str(a.jobs)]
        if a.pack_config:cmd+=['--config',a.pack_config]
        if a.max_cups:cmd+=['--max-cups',str(a.max_cups)]
        run(cmd)
    if a.check:log('check passed: ready to compile and package');return
    if a.cook_only:log('cook complete');return
    if not a.skip_compile:stage_compile(a.jobs)
    cia=stage_package(a.version,False,a.keep_stage or a.cci)
    if a.cci:stage_package(a.version,True,a.keep_stage)
    log('done:',cia)
    log('Copy it to your SD card and install it with FBI, or use FBI remote install.')
    log('For quick updates later, also copy build/release/sd-card/3ds to the root of your SD card (see README).')

if __name__=='__main__':main()
