#!/usr/bin/env python3
"""Grand Prix award ceremony, losing scene and ending stage.

Converted once with the 0.5.0 rebuild so the scenes can arrive as quick
updates: the stages (Race/Course/*_demo.szs) through the course importer,
the award characters (Demo/Award.szs: standing model with demowin/demooth),
podium blocks, shadow, trophies (Demo/Trophy) and the ceremony camera moves
(SCN0: 123dai demowin01-03, Lose demolos01). models/ceremony.json lists it all.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/gclib')]
from unpack_szs import unpack
from cook_model import cook
OUT=ROOT/'sd-card/3ds/mkw-3ds'
EXTRACTED=ROOT/'data/extracted'
WORK=ROOT/'build/ceremony'
# Kinoko course IDs (Common.hh COURSE_NAMES): the scenes' stages.
# draw_demo is not converted: retail's table names it "draw_dmeo", so the game
# never loads it (its textures are also an older TEX0 version).
STAGES=[(55,'winningrun_demo','Winning run'),(56,'loser_demo','Losing'),(58,'ending_demo','Ending')]
DISC_FILES=['Demo/','Race/Course/winningrun_demo.szs','Race/Course/loser_demo.szs','Race/Course/ending_demo.szs']
CUPS=['kinoko','flower','star','special','koura','banana','konoha','thunder','battle']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def extract(disc):
    missing=[f for f in DISC_FILES if not (EXTRACTED/f).exists()]
    if not missing:return
    if not disc:raise SystemExit('The ceremony files need the disc image: '+', '.join(missing))
    command=[sys.executable,str(ROOT/'tools/extract_disc.py'),str(disc),str(EXTRACTED)]
    for f in DISC_FILES:command+=['--prefix',f]
    subprocess.run(command,check=True)

def export(source,destination,model,*pose):
    destination.mkdir(parents=True,exist_ok=True)
    subprocess.run(['node',str(ROOT/'build/export_brres.mjs'),str(source),str(destination),model,*pose],check=True,stdout=subprocess.DEVNULL)

def model_names(path):
    """MDL0 names of a BRRES (its 3DModels group)."""
    import struct
    b=path.read_bytes();root=struct.unpack_from('>H',b,0xc)[0]
    def group(off):
        n=struct.unpack_from('>I',b,off+4)[0];out=[]
        for i in range(1,n+1):
            e=off+8+i*16;name_off,data_off=struct.unpack_from('>II',b,e+8)
            out.append((b[off+name_off:b.index(0,off+name_off)].decode(),off+data_off))
        return out
    groups=dict(group(root+8))
    return [n for n,_ in group(groups['3DModels(NW4R)'])] if '3DModels(NW4R)' in groups else []

def cook_static(source,model,name):
    work=WORK/'exports'/name;export(source,work,model)
    parts=cook(work,OUT,name,256,texture_prefix=name)
    if len(parts)!=1:raise ValueError(f'{name}: expected one model, got {len(parts)}')
    shutil.copyfile(OUT/'models'/(parts[0]['name']+'.gmdl'),OUT/'models'/(name+'.gmdl'))
    return name

def cook_award_character(source,code):
    """Standing award model (bound in its first demowin pose) and its demowin/demooth bank."""
    name='award_'+code;work=WORK/'exports'/name
    export(source,work,'model','demowin','0')
    parts=cook(work,OUT,name,256,preserve_vertices=True,texture_prefix=name)
    if len(parts)!=1:raise ValueError(f'{name}: expected one model, got {len(parts)}')
    shutil.copyfile(OUT/'models'/(parts[0]['name']+'.gmdl'),OUT/'models'/(name+'.gmdl'))
    bank=OUT/'models'/(name+'.dskm')
    audit=json.loads(subprocess.run(['node',str(ROOT/'build/export_driver.mjs'),str(source),str(bank)],check=True,capture_output=True,text=True).stdout)
    clips=[c['name'] if isinstance(c,dict) else c for c in audit['clips']]
    if not {'demowin','demooth'}<={*clips}:raise ValueError(f'{name}: award clips missing ({clips})')
    return {'code':code,'model':f'models/{name}.gmdl','bank':f'models/{name}.dskm','clips':clips}

def main():
    p=argparse.ArgumentParser();p.add_argument('disc',nargs='?');a=p.parse_args()
    extract(a.disc)
    WORK.mkdir(parents=True,exist_ok=True)
    manifest={'version':1,'stages':[],'award':{},'trophies':{},'cameras':[]}
    # Stages: the race course pipeline (models, sky, map, placed objects).
    from import_courses import import_one
    for i,key,name in STAGES:
        c={'id':i,'enum':key,'name':name,'kind':'race','cup':'Ceremony','slot':0,'archive':f'Race/Course/{key}.szs','key':key,'prefix':f'course_{i:02d}'}
        r=import_one(c)
        if r['status']!='imported':raise SystemExit(f'{name} stage: {r.get("error")}')
        manifest['stages'].append({'id':i,'key':key,'name':name,'receipt':f'models/courses/{i:02d}.json','model_lists':r['model_lists'],'object_visuals':r.get('object_visuals')})
    # Award characters (including the Mii bodies and the bike outfits ds3/pc3/rs3),
    # podium blocks and the shared shadow.
    award=WORK/'Award';unpack(EXTRACTED/'Demo/Award.szs',award)
    characters=[]
    # The archive also holds empty folders (Cup, Camera, Model, hiradai2.brres...).
    for source in sorted(p for p in award.glob('*.brres') if p.is_file()):
        models=model_names(source)
        if models==['model']:characters.append(cook_award_character(source,source.stem))
    manifest['award']['characters']=characters
    manifest['award']['stands']=[cook_static(award/'v_stand1.brres',m,'award_'+m) for m in model_names(award/'v_stand1.brres')]
    manifest['award']['shadow']=cook_static(award/'shadow.brres','shadow','award_shadow')
    for cup in CUPS:
        source=EXTRACTED/f'Demo/Trophy/{cup}_trophy.brres'
        manifest['trophies'][cup]=cook_static(source,f'{cup}_trophy',f'trophy_{cup}')
    # Camera moves (tools/ceremony/export_scene.ts).
    subprocess.run(['node','tools/ceremony/bundle.mjs'],cwd=ROOT,check=True)
    lose=WORK/'Lose';unpack(EXTRACTED/'Demo/Lose.szs',lose)
    cameras=OUT/'models/ceremony'
    if cameras.exists():shutil.rmtree(cameras)
    for source in (award/'123dai.brres',lose/'demolos01.brres'):
        out=subprocess.run(['node',str(ROOT/'build/ceremony/export_scene.mjs'),str(source),str(cameras)],check=True,capture_output=True,text=True).stdout
        for row in json.loads(out):manifest['cameras'].append({**row,'file':'models/ceremony/'+row['file']})
    manifest['sources']={f:digest(EXTRACTED/f) for f in ['Demo/Award.szs','Demo/Lose.szs']+[f'Demo/Trophy/{c}_trophy.brres' for c in CUPS]}
    (OUT/'models/ceremony.json').write_text(json.dumps(manifest,indent=1)+'\n')
    print(f"ceremony: {len(manifest['stages'])} stages, {len(characters)} award characters, {len(manifest['trophies'])} trophies, {len(manifest['cameras'])} camera moves")

if __name__=='__main__':main()
