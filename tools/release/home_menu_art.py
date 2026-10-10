#!/usr/bin/env python3
"""HOME Menu icon, banner image and banner sound, made from the player's disc.

Inputs are this tree's unpacked menu archives (assets/menu-ui, from the
player's Scene/UI) and the cooked title music (sd-card movies/title_bgm.wav).
Nothing here ships: the release builder runs it on the player's machine.
Outputs: icon.png (48x48, Mario in the Standard Kart), banner.png (256x128), banner.wav (16-bit stereo,
under 3 s, as the HOME Menu requires).
"""
import argparse, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/gclib')]
from cook_race_items import decode_tpl
UI=ROOT/'assets/menu-ui'

def title_scene():
    # The title screen as tools/cook_menu_ui.py composes it (832x456 canvas).
    title=Image.new('RGBA',(832,456),(255,255,255,255))
    title.alpha_composite(decode_tpl(UI/'Title/title/timg/tt_title_screen_mario2.tpl'),(0,140))
    title.alpha_composite(decode_tpl(UI/'Title_U/title/timg/tt_title_screen_title_rogo_r_only.tpl'),(0,0))
    return title.crop((112,0,720,456))

def banner(path):
    # The whole 608x456 title screen, fitted to the banner's height on the
    # title's own white backdrop (a 2:1 crop would cut the logo).
    scene=title_scene();w,h=scene.size;fit=scene.resize((w*128//h,128),Image.LANCZOS)
    out=Image.new('RGBA',(256,128),(255,255,255,255));out.alpha_composite(fit,((256-fit.width)//2,0));out.save(path)

def icon(path):
    # Mario in the Standard Kart, cut from the title screen art. That image
    # also holds the bottom of the Wii ring (top left) and the kart's grey
    # drop shadow; both are painted out to the white backdrop first.
    art=np.array(decode_tpl(UI/'Title/title/timg/tt_title_screen_mario2.tpl').convert('RGB')).astype(int)
    r,g,b=art[...,0],art[...,1],art[...,2];yy,xx=np.mgrid[:art.shape[0],:art.shape[1]]
    grey=art.max(-1)-art.min(-1)<25
    ring=(xx<510)&(yy<90)&~((r>g+40)&(r>b+40))
    shadow=grey&((xx<445)|((yy>245)&(xx<620)))
    art[ring|shadow]=255
    kart=Image.fromarray(art.astype(np.uint8)).crop((395,10,700,272))
    side=max(kart.size)+12;square=Image.new('RGB',(side,side),(255,255,255))
    square.paste(kart,((side-kart.width)//2,(side-kart.height)//2))
    square.resize((48,48),Image.LANCZOS).save(path)

def sound(source,path,seconds=2.9,fade=.4):
    with wave.open(str(source)) as w:
        if w.getsampwidth()!=2:raise SystemExit('expected 16-bit PCM title music')
        rate,channels=w.getframerate(),w.getnchannels()
        pcm=np.frombuffer(w.readframes(int(rate*seconds)),dtype='<i2').reshape(-1,channels).astype(np.float32)
    if channels==1:pcm=np.repeat(pcm,2,axis=1)
    ramp=np.ones(len(pcm),np.float32);n=int(rate*fade);ramp[-n:]=np.linspace(1,0,n)
    out=np.clip(pcm*ramp[:,None],-32768,32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(out.tobytes())

def make(out,music):
    out.mkdir(parents=True,exist_ok=True)
    icon(out/'icon.png');banner(out/'banner.png');sound(music,out/'banner.wav')
    return out/'icon.png',out/'banner.png',out/'banner.wav'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'build/release/art')
    p.add_argument('--music',type=Path,default=ROOT/'sd-card/3ds/mkw-3ds/movies/title_bgm.wav')
    a=p.parse_args()
    for f in make(a.output,a.music):print(f)
