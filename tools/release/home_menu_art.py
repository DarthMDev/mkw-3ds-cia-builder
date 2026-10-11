#!/usr/bin/env python3
"""HOME Menu icon, banner image and banner sound, made from the player's disc.

Inputs are this tree's unpacked menu archives (assets/menu-ui, from the
player's Scene/UI) and the cooked title music (sd-card movies/title_bgm.wav).
Nothing here ships: the release builder runs it on the player's machine.
Outputs: icon.png (48x48, the Standard Kart M), banner.png (256x128), banner.wav (16-bit stereo,
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
    # The Standard Kart M side view from the vehicle select screen (96x50),
    # centred on white.
    kart=decode_tpl(UI/'MenuSingle/control/timg/st_mdf_kart.tpl').convert('RGBA')
    kart=kart.resize((48,48*kart.height//kart.width),Image.LANCZOS)
    square=Image.new('RGBA',(48,48),(255,255,255,255))
    square.alpha_composite(kart,(0,(48-kart.height)//2))
    square.save(path)

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
