#!/usr/bin/env python3
"""Build selectable skin sound tables over one shared archive of voice payloads."""
import copy, hashlib, json, re, struct
from pathlib import Path
from nw4r_audio import Rsar, Rwar, Rbnk, Rwsd
from audio_reach import reach
from cook_audio import loop_bridge
from cook_roster import ROSTER, ROOT
from cook_garage_skins import CHARACTER_DIR

def main():
    original=(ROOT/'data/extracted/sound/revo_kart.brsar').read_bytes()
    r=Rsar(original)
    base=(ROOT/'build/audio/audio/sound.arc').read_bytes()
    counts=struct.unpack_from('<10I',base,8)
    ns,nf,nb,ng,ni,np,nt,nbridge,nwave,nreach=counts
    file_at=64+ns*44
    wave_at=file_at+nf*24+nb*4+ng*8+ni*4+np+nt+nbridge*28
    files=[list(struct.unpack_from('<6I',base,file_at+i*24)) for i in range(nf)]
    old_waves=[[] for _ in files];at=wave_at
    for i,f in enumerate(files):
        old_waves[i]=[struct.unpack_from('<2I',base,at+j*8) for j in range(f[4])];at+=f[4]*8
    prefix=base[file_at+nf*24:wave_at-nbridge*28]
    old_bridges=[base[wave_at-nbridge*28+i*28:wave_at-nbridge*28+(i+1)*28] for i in range(nbridge)]
    image=bytearray(original);variants={};payloads={};donors={};donor_files={}
    group_by_name={g['name']:g for g in r.groups}
    ids={code.upper():cid for slug,name,cid,code,size in ROSTER}
    codes={cid:code.upper() for slug,name,cid,code,size in ROSTER}
    donor_codes={slug:code.upper() for slug,name,cid,code,size in ROSTER}
    sounds_by_name={s["name"]:s for s in r.sounds}
    for path in sorted((CHARACTER_DIR/'Sound').iterdir()):
        match=re.match(r'(GRP_VO_([A-Z]+))-(\d+)(.*)\.(brwsd|brbnk)(?:\.[a-z_]+)?$',path.name)
        if match:
            group=group_by_name.get(match[1]+match[4]);cid=ids.get(match[2]);slot=int(match[3])
            if group is None or cid is None:continue
            data=path.read_bytes();magic=data[:4]
            target=next((it['fileId'] for it in group['items'] if r.file_bytes(it['fileId'])[0][:4]==magic),None)
        else:
            match=re.match(r'(\d+)\.([a-z]+)-(\d+)\.brbnk(?:\.[a-z_]+)?$',path.name)
            if not match or match[2].upper() not in ids:continue
            target=int(match[1]);cid=ids[match[2].upper()];slot=int(match[3]);data=path.read_bytes();magic=data[:4]
            if target>=nf or r.file_bytes(target)[0][:4]!=magic:continue
        if target is None:continue
        suffix=path.name.rsplit('.',1)[-1]
        if suffix in donor_codes and match and match[1].startswith('GRP_VO_'):
            donor=donor_codes[suffix];donors[(cid,slot)]=donor
            source_group=group_by_name.get((match[1]+match[4]).replace('_'+codes[cid], '_'+donor,1))
            if source_group:
                source_fid=next((it['fileId'] for it in source_group['items'] if r.file_bytes(it['fileId'])[0][:4]==data[:4]),None)
                if source_fid is not None:donor_files.setdefault((cid,slot),{})[source_fid]=target
        size=struct.unpack_from('>I',data,8)[0]
        if magic not in (b'RWSD',b'RBNK') or size>len(data):raise ValueError(path)
        main=data[:size];wave_start=data.find(b'RWAR',size);wave=data[wave_start:] if wave_start>=0 else b''
        if wave and wave[:4]!=b'RWAR':raise ValueError('Missing paired RWAR: '+path.name)
        (Rwsd if magic==b'RWSD' else Rbnk)(main)
        key=hashlib.sha256(data).digest()
        if key not in payloads:
            image.extend(bytes(-len(image)%32));off=len(image);image.extend(data);payloads[key]=off
        off=payloads[key]
        variants.setdefault((cid,slot),{})[target]=(off,len(main),off+wave_start if wave else 0,len(wave),main,wave)
    out=ROOT/'build/skin-audio/audio';(out/'skins').mkdir(parents=True,exist_ok=True)
    (out/'skin-voices.brsar').write_bytes(image)
    retail_reach_at=wave_at+nwave*8
    retail_pool_at=retail_reach_at+ns*8
    retail_reach={}
    for i in range(ns):
        first,count=struct.unpack_from('<2I',base,retail_reach_at+i*8)
        retail_reach[i]=list(struct.unpack_from(f'<{count}H',base,retail_pool_at+first*2))
    entries=[]
    for (cid,slot),overrides in sorted(variants.items()):
        fs=copy.deepcopy(files);waves=copy.deepcopy(old_waves);rr=copy.deepcopy(r);rr.data=image
        bridges=[b for b in old_bridges if struct.unpack_from('<I',b)[0] not in overrides]
        for fid,(mo,ms,wo,ws,main,wave) in overrides.items():
            rw=Rwar(wave) if wave else None;wc=len(rw.waves) if rw else 0
            fs[fid]=[mo,ms,wo,ws,wc,files[fid][5]]
            waves[fid]=[]
            if rw:
                tab=struct.unpack_from('>I',wave,0x10)[0];dataoff=struct.unpack_from('>I',wave,0x18)[0]
                waves[fid]=[(dataoff+struct.unpack_from('>I',wave,tab+16+i*12)[0],struct.unpack_from('>I',wave,tab+20+i*12)[0]) for i in range(wc)]
                for wi,w in enumerate(rw.waves):
                    if w.format==2 and w.loop and w.loop_start%14:
                        for ch in range(w.channels):
                            b=loop_bridge(wave,w,ch)
                            if b:bridges.append(struct.pack('<IH',fid,wi)+b[6:])
            # Reach readers follow the first group location for each file.
            gid,index=rr.files[fid]['positions'][0];g=rr.groups[gid];it=g['items'][index]
            it.update(offset=mo-g['offset'],size=ms,waveDataOffset=wo-g['waveDataOffset'],waveDataSize=ws)
        sound_bytes=bytearray(base[64:file_at]);muted=0;selected=[];changed_sounds=set()
        donor=donors.get((cid,slot));file_map=donor_files.get((cid,slot),{})
        for original_sound in r.sounds:
            sound=copy.deepcopy(original_sound)
            if donor and ('_'+codes[cid]+'_') in sound['name']:
                replacement=sounds_by_name.get(sound['name'].replace('_'+codes[cid]+'_','_'+donor+'_',1))
                if replacement is None:
                    sound_bytes[sound['id']*44]=0;muted+=1;continue
                sound=copy.deepcopy(replacement);sound['id']=original_sound['id'];sound['name']=original_sound['name'];changed_sounds.add(sound['id'])
                sound['fileId']=file_map.get(sound['fileId'],sound['fileId'])
                if sound['type']==1:
                    source_bank=r.banks[sound['seq']['bankId']]['fileId']
                    target_bank=file_map.get(source_bank,source_bank)
                    sound['seq']['bankId']=next(b['id'] for b in r.banks if b['fileId']==target_bank)
                # Sound names stay in the runtime's base-character slots; their
                # sequence/wave indices follow the donor's template layout.
                start=sound['id']*44;source=base[64+replacement['id']*44:64+(replacement['id']+1)*44]
                sound_bytes[start:start+44]=source
                struct.pack_into('<I',sound_bytes,start+16,sound['fileId'])
                if sound['type']==1:struct.pack_into('<H',sound_bytes,start+14,sound['seq']['bankId'])
            selected.append(sound)
        rr.sounds=[s for s in selected if s['id'] in changed_sounds or s['fileId'] in overrides or
            (s['type']==1 and r.banks[s['seq']['bankId']]['fileId'] in overrides)]
        reachable=reach(rr);pool=[];reach_entries=[]
        for s in r.sounds:
            _,ww=reachable.get(s['id'],(None,retail_reach[s['id']]));
            fid=reachable.get(s['id'],(None,[]))[0]
            if fid is not None and any(w>=fs[fid][4] for w in ww):
                # Some supplied replacements deliberately contain no wave data.
                # Disable that sound instead of resolving an invalid wave index.
                sound_bytes[s['id']*44]=0;ww=[];muted+=1
            reach_entries.append((len(pool),len(ww)));pool.extend(ww)
        header=bytearray(base[:64]);struct.pack_into('<I',header,36,len(bridges));struct.pack_into('<I',header,40,sum(len(w) for w in waves));struct.pack_into('<I',header,44,len(pool))
        blob=header+sound_bytes+b''.join(struct.pack('<6I',*f) for f in fs)+prefix
        bridges.sort(key=lambda b:struct.unpack_from('<IHB',b))
        blob+=b''.join(bridges)+b''.join(struct.pack('<2I',*w) for ff in waves for w in ff)
        blob+=b''.join(struct.pack('<2I',*e) for e in reach_entries)+b''.join(struct.pack('<H',w) for w in pool)
        blob+=bytes(-len(blob)%4)
        name=f'skins/{cid}_{slot}.arc';(out/name).write_bytes(blob)
        entries.append({'path':name,'sha256':hashlib.sha256(blob).hexdigest(),'files':len(overrides)})
        print(cid,slot,len(overrides),'voice files',flush=True)
    manifest={'archiveSha256':hashlib.sha256(image).hexdigest(),'variants':entries}
    (out/'skins.json').write_text(json.dumps(manifest,indent=2))
    print('Built',len(entries),'skin sound tables; archive bytes',len(image))
if __name__=='__main__':main()
