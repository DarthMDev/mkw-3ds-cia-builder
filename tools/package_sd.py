#!/usr/bin/env python3
"""Stage a private playable SD package from the user's locally cooked assets."""
import hashlib,json,shutil,struct,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];assets=ROOT/'sd-card/3ds/mkw-3ds';out=ROOT/'build/playable/3ds/mkw-3ds';out.mkdir(parents=True,exist_ok=True)
roster_overlay=ROOT/'build/roster'
def roster_asset(relative):
 relative=Path(relative)
 if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid roster asset path')
 candidate=roster_overlay/relative
 return candidate if candidate.is_file() else assets/relative
# Explicit allowlist excludes QA markers, ghosts, receipts and obsolete models.
files={ROOT/'build/mkw-3ds.3dsx':Path('mkw-3ds.3dsx'),ROOT/'data/extracted/Race/Common.szs':Path('Race/Common.szs')}
catalog=json.loads((assets/'models/course-catalog.json').read_text())
if catalog.get('version')!=1 or len(catalog.get('courses',[]))!=42:raise ValueError('Import all 32 races and 10 arenas before packaging')
files[assets/'models/course-catalog.json']=Path('models/course-catalog.json')
models=['coconut_palm_000','coconut_escalator_000']
for course in catalog['courses']:
 if course['status']!='imported':raise ValueError('Course import failed: '+course['name'])
 archive=Path(course['archive']);receipt=Path(course['receipt'])
 if archive.parent!=Path('Race/Course') or archive.suffix!='.szs' or receipt.parent!=Path('models/courses'):raise ValueError('Invalid course path')
 source=ROOT/'data/extracted'/archive
 if hashlib.sha256(source.read_bytes()).hexdigest()!=course['archive_sha256']:raise ValueError('Source archive changed: '+course['name'])
 files[source]=archive;files[assets/receipt]=receipt
 # Placed objects: tools/cook_course_objects.py meshes and animation banks.
 visuals=assets/f"models/course_{course['id']:02d}_visuals.list"
 if course['kind']=='race':
  if not visuals.is_file():raise ValueError('Cook course objects before packaging: '+course['name'])
  files[visuals]=Path('models')/visuals.name
  for line in visuals.read_text().splitlines():
   resource,model,mesh,bank=line.split()
   for name in (mesh,bank):
    if name!='-' and any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in name):raise ValueError('Invalid course object name')
   models.append(mesh)
   if bank!='-':files[assets/'models'/(bank+'.dobj')]=Path('models')/(bank+'.dobj')
 for name in course['model_lists']:
  relative=Path(name)
  if relative.parent!=Path('models') or relative.suffix!='.list':raise ValueError('Invalid course model list')
  # Superseded merged per-archive object meshes (pre-visuals importer).
  if relative.stem.startswith(f"course_{course['id']:02d}_obj_"):continue
  files[assets/relative]=relative
  for model in (assets/relative).read_text().split():
   if not model or any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in model):raise ValueError('Invalid course model name')
   models.append(model)
roster=json.loads(roster_asset('models/roster.json').read_text())
if roster.get('version')!=1 or len(roster.get('characters',[]))!=24:raise ValueError('Cook all 24 retail drivers with tools/cook_full_roster.py before packaging')
files[roster_asset('models/roster.json')]=Path('models/roster.json')
garage=json.loads(roster_asset('models/garage.json').read_text())
if garage.get('version')!=1 or len(garage.get('choices',[]))!=288:raise ValueError('Cook all 288 retail driver/vehicle combinations before packaging')
files[roster_asset('models/garage.json')]=Path('models/garage.json')
for choice in garage['choices']:
 prefix=choice['prefix']
 if not prefix or any(c not in 'abcdefghijklmnopqrstuvwxyz_' for c in prefix):raise ValueError('Invalid garage prefix')
 for name in choice['models']:
  if not name.startswith(prefix) or any(c not in 'abcdefghijklmnopqrstuvwxyz_' for c in name):raise ValueError('Invalid garage model name')
  models.append(name)
 for name in choice['animationBanks']:
  if name not in choice['models']:raise ValueError('Animation bank has no matching model')
  files[roster_asset(Path('models')/(name+'.dskm'))]=Path('models')/(name+'.dskm')
textures={'drift_sparkTex2','drift_flash2','drift_rk_smoke2'}
files[assets/'textures/drift-effects.bin']=Path('textures/drift-effects.bin')
files[assets/'textures/drift-effects-bike.bin']=Path('textures/drift-effects-bike.bin')
menu_ui=json.loads((assets/'models/menu-ui.json').read_text())
if menu_ui.get('version') not in (1,2) or len(menu_ui.get('maps',[]))!=32:raise ValueError('Cook source layouts for all 32 race maps before packaging')
files[assets/'models/menu-ui.json']=Path('models/menu-ui.json')
def digest_file(path):
 digest=hashlib.sha256()
 with path.open('rb') as source:
  for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()
# Validate source receipts before mixing cooked UI revisions into a package.
for name,expected in menu_ui.get('sourceHashes',{}).items():
 source=ROOT/name
 if '..' in Path(name).parts or not source.is_file() or digest_file(source)!=expected:raise ValueError('Menu UI source changed: '+name)
movie_manifest=json.loads((assets/'models/menu-movies.json').read_text())
if movie_manifest.get('version')!=1 or not movie_manifest.get('everySourceFrame') or len(movie_manifest.get('streams',[]))<17:raise ValueError('Cook complete retail menu movies before packaging')
files[assets/'models/menu-movies.json']=Path('models/menu-movies.json')
for movie in movie_manifest['streams']:
 relative=Path(movie['path']);source_relative=Path(movie['source']);source=ROOT/source_relative
 if relative.parent!=Path('movies') or relative.suffix!='.gmv' or '..' in source_relative.parts or not str(source_relative).startswith('data/extracted/thp/'):raise ValueError('Invalid menu movie path')
 if digest_file(source)!=movie['sourceSha256']:raise ValueError('Menu movie source changed: '+str(source_relative))
 path=assets/relative
 with path.open('rb') as stream:header=stream.read(64)
 if len(header)!=64:raise ValueError('Truncated GMV header')
 magic,version,width,height,count,numerator,denominator,frame_bytes,offset=struct.unpack('<4sIHHIIIII32x',header)
 if magic!=b'GMV1' or version!=1 or [width,height]!=movie['textureSize'] or count!=movie['frames'] or numerator!=movie['fpsNumerator'] or denominator!=movie['fpsDenominator'] or frame_bytes!=width*height//2 or offset!=64 or path.stat().st_size!=64+count*frame_bytes:raise ValueError('Invalid full-rate GMV stream: '+str(relative))
 if digest_file(path)!=movie.get('sha256'):raise ValueError('Menu movie payload changed: '+str(relative))
 files[path]=relative
intro_audio=movie_manifest['introAudio'];audio_relative=Path(intro_audio['path'])
if audio_relative!=Path('movies/title.wav') or digest_file(assets/audio_relative)!=intro_audio['sha256']:raise ValueError('Opening movie audio changed')
if digest_file(ROOT/intro_audio['source'])!=intro_audio['sourceSha256']:raise ValueError('Opening movie audio source changed')
files[assets/audio_relative]=audio_relative
menu_audio=json.loads((assets/'models/menu-audio.json').read_text())
if menu_audio.get('version')!=1 or digest_file(ROOT/menu_audio['source'])!=menu_audio['sourceSha256']:raise ValueError('Title music source changed')
files[assets/'models/menu-audio.json']=Path('models/menu-audio.json')
for sound in menu_audio['waves']:
 relative=Path(sound['path'])
 if relative.parent!=Path('movies') or relative.suffix!='.wav' or digest_file(assets/relative)!=sound['sha256']:raise ValueError('Title music payload changed')
 files[assets/relative]=relative


for sprite in menu_ui['sprites'].values():
 relative=Path(sprite['path'])
 if relative.parent!=Path('textures') or relative.suffix!='.t3x':raise ValueError('Invalid menu UI texture path')
 textures.add(relative.stem)
menu_models=json.loads((assets/'models/menu-models.json').read_text())
files[assets/'models/menu-models.json']=Path('models/menu-models.json')
for entry in menu_models['models']:
 prefix=entry['prefix'];model=entry['model']['name']
 if not prefix.startswith(('ui_driver_','ui_back_','ui_machine_')) or any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in prefix):raise ValueError('Invalid menu model prefix')
 if model!=prefix+'_000':raise ValueError('Invalid menu model name')
 models.append(model)
 animation=assets/'models'/(prefix+'.dskm')
 if entry.get('animation'):
  if hashlib.sha256(animation.read_bytes()).hexdigest()!=entry['animation_sha256']:raise ValueError('Menu animation changed: '+prefix)
  files[animation]=Path('models')/animation.name
race_items=json.loads((assets/'models/race-items.json').read_text())
if race_items.get('version')!=1:raise ValueError('Cook current race item/HUD assets before packaging')
files[assets/'models/race-items.json']=Path('models/race-items.json')
for item in [*race_items['items'].values(),race_items['itemBox'],race_items['startSignal'],race_items['bombCore']]:
 relative=Path(item['path'])
 if relative.parent!=Path('models') or relative.suffix!='.gmdl':raise ValueError('Invalid race item model path')
 models.append(relative.stem)
 if item.get('animation'):
  animation=Path(item['animation'])
  if animation!=relative.with_suffix('.dskm'):raise ValueError('Invalid race item animation path')
  files[assets/animation]=animation
for category in ['hudItems','hudRanks','hudDigits','hudExtras']:
 for sprite in race_items[category].values():
  relative=Path(sprite['path'])
  if relative.parent!=Path('textures') or relative.suffix!='.t3x':raise ValueError('Invalid race HUD texture path')
  textures.add(relative.stem)
for name in models:
 p=roster_asset(Path('models')/(name+'.gmdl'));b=p.read_bytes();magic,version,nv,ni,ns,nt=struct.unpack_from('<4s5I',b)
 if magic!=b'GMDL' or version not in (3,4):raise ValueError('Regenerate GMDL v3/v4: '+str(p))
 stride=44 if version==3 else 56 # v4: retail course lighting (tools/gx_material.py)
 for i in range(nt):textures.add(b[24+ns*stride+i*64:24+ns*stride+(i+1)*64].split(b'\0')[0].decode())
 files[p]=Path('models')/p.name
for name in sorted(textures):files[roster_asset(Path('textures')/(name+'.t3x'))]=Path('textures')/(name+'.t3x')
# Race VFX cooked in this tree (tools/cook_race_effects.py, tools/cook_effects.py
# --output build/vfx/textures) replace or extend the shared SD assets.
vfx=ROOT/'build/vfx/textures'
if not (vfx/'race-effects.bin').is_file():raise ValueError('Run tools/cook_race_effects.py before packaging')
effect_table=(vfx/'race-effects.bin').read_bytes()
overlay={'textures/race-effects.bin':vfx/'race-effects.bin'}
# REFX v3 (NW4R EF resources): a 20-byte header, then 40-byte texture entries (name,
# GX and padded sizes).
if struct.unpack_from('<4sI',effect_table)!=(b'REFX',3):raise ValueError('race-effects.bin is not REFX v3')
for i in range(struct.unpack_from('<I',effect_table,12)[0]):
 name=effect_table[20+i*40:52+i*40].split(b'\0')[0].decode()
 if not name.startswith('fx_') or any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in name):raise ValueError('Invalid effect texture name')
 overlay['textures/'+name+'.t3x']=vfx/(name+'.t3x')
for name in ('drift-effects.bin','drift-effects-bike.bin'):
 if (vfx/name).is_file():overlay['textures/'+name]=vfx/name
# CtrlRaceNameBalloon names and line (tools/cook_race_balloon.py).
for extra in sorted(vfx.glob('hud_*.t3x')):overlay['textures/'+extra.name]=extra
# Lakitu (tools/cook_lakitu.py): models, CHR0 banks, joint tracks, textures.
vfx_models=ROOT/'build/vfx/models'
for name in ('body','rod','flag','signal','lap','lapf','reverse'):
 model=vfx_models/f'lakitu_{name}.gmdl'
 if not model.is_file():raise ValueError('Run tools/cook_lakitu.py before packaging')
 overlay['models/'+model.name]=model
 b=model.read_bytes();ns,nt=struct.unpack_from('<II',b,16)
 for i in range(nt):
  tex=b[24+ns*44+i*64:24+ns*44+(i+1)*64].split(b'\0')[0].decode();overlay['textures/'+tex+'.t3x']=vfx/(tex+'.t3x')
for extra in ('lakitu_body.dskm','lakitu_rod.dskm','lakitu_flag.dskm','lakitu_body.djnt','lakitu_rod.djnt'):overlay['models/'+extra]=vfx_models/extra
# Course/sky meshes and receipts re-cooked in this tree (tools/cook_course_overlay.py);
# part lists and textures are unchanged, so only these files are replaced.
course_overlay=ROOT/'build/course-materials';packaged={r.as_posix() for r in files.values()}
for src in sorted(course_overlay.glob('models/*.gmdl'))+sorted(course_overlay.glob('models/courses/*.json')):
 rel=src.relative_to(course_overlay).as_posix()
 if src.name.startswith('._'):continue
 if rel not in packaged:raise ValueError('Course overlay file is not packaged: '+rel)
 overlay[rel]=src
# Race-flow UI (tools/cook_race_flow.py): out-of-bounds wipe, result board and
# end-of-race menu textures, cooked into this tree's own overlay directory.
flow=ROOT/'build/race-flow/textures'
if not (flow/'flow_wipe.t3x').is_file():raise ValueError('Run tools/cook_race_flow.py before packaging')
for extra in sorted(flow.glob('flow_*.t3x')):
 if not extra.name.startswith('._'):overlay['textures/'+extra.name]=extra
# Race bottom screen (tools/cook_race_map.py): 32 course maps, their overviews
# and the UI atlas, cooked into this tree's own overlay directory.
race_map=ROOT/'build/race-map/textures'
if not (race_map/'race_bottom_ui.t3x').is_file():raise ValueError('Run tools/cook_race_map.py before packaging')
for extra in sorted(race_map.glob('race_*.t3x')):
 if not extra.name.startswith('._'):overlay['textures/'+extra.name]=extra
# Sound engine (tools/cook_audio.py): the cooked tables from build/audio and
# the user's retail BRSAR and BRSTM streams, unmodified, read by offset.
audio_manifest=ROOT/'build/audio/audio/manifest.json'
if not audio_manifest.is_file():raise ValueError('Run tools/cook_audio.py before packaging')
audio=json.loads(audio_manifest.read_text())
sound_source=ROOT/'data/extracted/sound'
if audio.get('version')!=1 or digest_file(ROOT/audio['source'])!=audio['sourceSha256']:raise ValueError('Sound archive changed: rerun tools/cook_audio.py')
if hashlib.sha256((ROOT/'build/audio/audio/sound.arc').read_bytes()).hexdigest()!=audio['arcSha256']:raise ValueError('sound.arc does not match its manifest')
overlay['audio/sound.arc']=ROOT/'build/audio/audio/sound.arc'
overlay['audio/revo_kart.brsar']=ROOT/audio['source']
for rel,info in audio['streams'].items():
 stream=sound_source/rel
 if Path(rel).parent!=Path('strm') or stream.suffix!='.brstm' or stream.stat().st_size!=info['bytes']:raise ValueError('Sound stream changed: '+rel)
 overlay['audio/'+rel]=stream
# Blue Shell / Bob-omb blast with raw UVs for its retail binder (tools/cook_blast.py).
blast=vfx_models/'bomb_blast.gmdl'
if not blast.is_file():raise ValueError('Run tools/cook_blast.py before packaging')
overlay['models/bomb_blast.gmdl']=blast
b=blast.read_bytes();ns,nt=struct.unpack_from('<II',b,16)
for i in range(nt):
 tex=b[24+ns*44+i*64:24+ns*44+(i+1)*64].split(b'\0')[0].decode();overlay['textures/'+tex+'.t3x']=vfx/(tex+'.t3x')
for rel,src in overlay.items():
 for old in [s for s,r in files.items() if r==Path(rel)]:del files[old]
 files[src]=Path(rel)
import sys
# Indexed archives (tools/pack_menu_assets.py, tools/pack_race_assets.py): the
# runtime reads packed assets with one open handle; loose files remain as a
# fallback for anything not packed.
for archive in ('menu.pak','race.pak'):
 if (assets/archive).is_file():files[assets/archive]=Path(archive)
if '--list' in sys.argv:
 print(json.dumps({str(rel):str(src) for src,rel in files.items()}))
 raise SystemExit(0)
manifest={}
for src,rel in files.items():
 dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);manifest[str(rel)]=hashlib.sha256(dest.read_bytes()).hexdigest()
controls='''MKW 3DS - native Wii menu asset port, 32 race archives and 10 arena asset sets
Copy the 3ds folder to the SD card root. Launch mkw-3ds.3dsx with Homebrew Launcher.
Menu: D-pad / Circle Pad choose, A confirm, B back. A or START skips the opening.
The opening retains every retail movie frame and its original stereo soundtrack.
The title screen uses its original BRSAR wave and authored loop point.
Audio requires a working 3DS DSP service; missing DSP leaves video playback usable.
All menus use the top LCD. The lower LCD is unused during menu selection.
During races the lower LCD shows the course map, the standings and the time;
tap it to switch between the close-up map and the whole course.
To race: Single Player > VS > Solo, then any of the 24 retail characters and one
of the six vehicles in the top three rows, drift, a cup and any of the 32 courses.
Grand Prix, Time Trials, Battle, Team VS, the remaining vehicle choices and
the two Mii outfits can be browsed but show "Not available" on the page where they
are chosen; nothing silently starts a different mode. Licenses are session slots,
not an implementation of Wii save profiles, unlocks, Mii creation or statistics.
Each race opens with the course's original preview cameras; A or START skips it.
Race: Circle Pad steer; A accelerate; B brake; R hop/drift; L use item;
D-pad trick; START pause. Pause offers continue, restart, or quit confirmation.
After finishing, press A for results. Next Race returns to course selection;
the final race returns to the main menu. VS races have 12 racers.
Bike: D-pad up starts a wheelie; down ends it.
Original source THP menu atlases stream at their native frame rates. Menu backgrounds,
character and vehicle displays use original source models and animations.
All 32 courses and 10 arenas are imported; arena race rules are not implemented.
Race music, kart sounds, character voices, item sounds and course sound events
use the original sound archive. Menu sound effects and selection music are present.
Online play, persistent profiles, the Mii identity path and unsupported race modes
remain unfinished. Rosalina's separate Luma companion is not yet rendered.
This expanded roster needs console playtesting; this is not complete Wii parity.
Original local game assets are packaged privately for this user's device.
Do not replace only the executable; use the complete package.
'''

(out/'CONTROLS.txt').write_text(controls);manifest['CONTROLS.txt']=hashlib.sha256((out/'CONTROLS.txt').read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# This directory is generated package staging. Keep it as strict as the ZIP,
# so copying the staged 3ds folder cannot retain obsolete replay/QA assets.
for stale in out.rglob('*'):
 if stale.is_file() and stale.relative_to(out).as_posix() not in {*manifest,'manifest.json'}:stale.unlink()
if '--no-zip' in sys.argv:
 print(json.dumps({'staged':str(out),'files':len(manifest)+1},indent=2))
 raise SystemExit(0)
zip_path=ROOT/'build/mkw-3ds-SD.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for rel in [*manifest,'manifest.json']:z.write(out/rel,Path('3ds/mkw-3ds')/rel)
print(json.dumps({'package':str(zip_path),'files':len(manifest)+1,'bytes':zip_path.stat().st_size,'sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest()},indent=2))
