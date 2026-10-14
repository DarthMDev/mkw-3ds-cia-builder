#!/usr/bin/env python3
"""Cook each named Retro Rewind variant from its own local source archive."""
import json,argparse,concurrent.futures
from pathlib import Path
from import_pulsar_pack import ROOT,convert_track
SOURCE=Path('/Users/michael/Library/Application Support/Dolphin/Load/Riivolution/WheelWizard/RetroRewind6/Tracks')
OUT=ROOT/'sd-card/3ds/mkw-3ds'
VARIANTS={'rMC1','rDP1','rGV1','rBC1','rCI1','rCI2','rVL1','rVL2','rRR1','rRR2'}
def cook_models():
 path=OUT/'pulsar_manifest.json';manifest=json.loads(path.read_text());count=0
 for cup in manifest['cups']:
  for track in cup['tracks']:
   stem=Path(track['archive']).stem
   if stem not in VARIANTS:continue
   assets=convert_track(SOURCE/(stem+'.szs'),OUT,'pulsar_variant_'+stem.lower())
   if not assets['models']:raise RuntimeError('Variant geometry missing: '+stem)
   track.update(assets);count+=1
 if count!=len(VARIANTS):raise RuntimeError('Missing variant catalog rows')
 path.write_text(json.dumps(manifest,indent=2)+'\n');print('Cooked',count,'independent variant model lists')
def cook_maps(out):
 from cook_retro_race_maps import bake_single_track
 tracks=[t for c in json.loads((OUT/'pulsar_manifest.json').read_text())['cups'] for t in c['tracks']]
 results={}
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
  jobs={pool.submit(bake_single_track,i,t['name'],t['archive'],t['models'],out):i for i,t in enumerate(tracks) if Path(t['archive']).stem in VARIANTS}
  for future in concurrent.futures.as_completed(jobs):
   data,error=future.result();i=jobs[future]
   if error:raise RuntimeError(error)
   results[i]=data;print(tracks[i]['name'],'map complete',flush=True)
 (out/'maps.json').write_text(json.dumps(results,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--maps-only',action='store_true');parser.add_argument('--map-output',type=Path)
 args=parser.parse_args()
 if not args.maps_only:cook_models()
 if args.map_output:cook_maps(args.map_output)
if __name__=='__main__':main()
