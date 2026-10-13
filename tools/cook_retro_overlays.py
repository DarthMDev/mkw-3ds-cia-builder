#!/usr/bin/env python3
"""Cook Retro Rewind race credits and custom minimap portraits from local assets."""
import json,re,struct,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from cook_roster import ROOT,ROSTER
from cook_garage_skins import CHARACTER_DIR
from cook_race_hud import font_strings
from cook_race_items import decode_tpl,cook_image_sprite
from devkitpro import tool
OUT=ROOT/'sd-card/3ds/mkw-3ds'

def text(image,color,height):
    a=np.array(image.convert('RGBA'));a[:,:,:3]=(a[:,:,:3].astype(np.uint16)*np.array(color[:3],dtype=np.uint16)//255).astype(np.uint8)
    result=Image.fromarray(a);return result.resize((max(1,round(result.width*height/result.height)),height),Image.Resampling.LANCZOS)

def main():
    manifest=json.loads((OUT/'pulsar_manifest.json').read_text());tracks=[t for c in manifest['cups'] for t in c['tracks']]
    labels={t['name'] for t in tracks}|{t.get('author','') for t in tracks}|{'Music: '+t['music_credit'] for t in tracks if t.get('music_credit')}
    labels|={t['name'].split(' ')[0]+' ' for t in tracks};labels.discard('')
    glyphs=font_strings(ROOT/'assets/race-ui/Font/kart_kanji_font.brfnt',sorted(labels))
    gold=(255,255,198);pink=(255,143,133);rows=[]
    for index,t in enumerate(tracks):
        title=text(glyphs[t['name']],gold,24)
        prefix=t['name'].split(' ')[0]+' '
        if prefix.strip() in ('SNES','N64','GBA','GCN','DS','Wii','3DS','Wii U','SW2','RMX','Tour','GP'):
            end=round(glyphs[prefix].width*24/glyphs[t['name']].height)
            original=text(glyphs[t['name']],pink,24);title.paste(original.crop((0,0,min(end,title.width),24)),(0,0))
        author=text(glyphs[t['author']],gold,19) if t.get('author') else None
        width=max(title.width,author.width if author else 0);im=Image.new('RGBA',(width,46 if author else 24));im.alpha_composite(title,(0,0))
        if author:im.alpha_composite(author,(0,27))
        if im.width>372:im=im.resize((372,round(im.height*372/im.width)),Image.Resampling.LANCZOS)
        track=cook_image_sprite(im,f'race_credit_track_{index}',OUT)
        music=None
        if t.get('music_credit'):
            im=text(glyphs['Music: '+t['music_credit']],gold,20)
            if im.width>372:im=im.resize((372,round(im.height*372/im.width)),Image.Resampling.LANCZOS)
            music=cook_image_sprite(im,f'race_credit_music_{index}',OUT)
        rows.append((track,music))
    lines=['#pragma once','#include <array>','namespace mkw {','struct CreditSprite {const char* path;float w,h,u,v;};','struct CreditRow {CreditSprite track,music;};',f'inline constexpr std::array<CreditRow,{len(rows)}> RaceCreditRows{{{{']
    def value(r):return '{nullptr,0,0,0,0}' if r is None else '{"textures/%s.t3x",%.6ff,%.6ff,%.6ff,%.6ff}'%(r['name'],r['width'],r['height'],r['u'],r['v'])
    for track,music in rows:lines.append('    {'+value(track)+','+value(music)+'},')
    lines+=['}};','}'];(ROOT/'include/mkw/race_credit_assets.hpp').write_text('\n'.join(lines)+'\n')
    # Replace the player's retail face rectangle in the existing UI atlas.
    header=(ROOT/'include/mkw/race_map_assets.hpp').read_text();block=header.split('RaceMapFaces{{',1)[1].split('}};',1)[0]
    rects=[tuple(map(int,m)) for m in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}',block)]
    ids={code:cid for _,_,cid,code,_ in ROSTER};base=Image.open(ROOT/'build/race-map/textures/race_bottom_ui.png').convert('RGBA');count=0
    for p in sorted((CHARACTER_DIR/'Map').glob('*.tpl')):
        parts=p.stem.split('-')
        if len(parts)!=2 or parts[0] not in ids or not parts[1].isdigit():continue
        cid,slot=ids[parts[0]],int(parts[1]);x,y,w,h=rects[cid];image=base.copy();face=decode_tpl(p).convert('RGBA').resize((w,h),Image.Resampling.LANCZOS)
        image.paste(face,(x,y));image.paste(face.crop((0,0,w,1)),(x,y-1));image.paste(face.crop((0,h-1,w,h)),(x,y+h))
        image.paste(face.crop((0,0,1,h)),(x-1,y));image.paste(face.crop((w-1,0,w,h)),(x+w,y))
        target=OUT/'textures'/f'race_bottom_skin_{cid}_{slot}.png';image.save(target)
        subprocess.run([str(tool('tex3ds')),'-f','rgba8','-z','none','-o',str(target.with_suffix('.t3x')),str(target)],check=True,stdout=subprocess.DEVNULL);count+=1
    print('Cooked',len(rows),'track credits and',count,'skin minimap atlases')
if __name__=='__main__':main()
