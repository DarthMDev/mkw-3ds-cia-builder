#!/usr/bin/env python3
"""Strip unused visual BRRES assets and custom engine files from course SZS archives.

Kinoko (simulation/physics) only requires:
- course.kmp
- course.kcl
- object .kcl files (e.g. WLwallGC.kcl, WLdokanGC.kcl, Mdush.kcl)
- effect / posteffect files (particles, lighting)
- ObjFlow.bin
Visual models and textures (.brres) are rendered natively from .gmdl/.t3x on the 3DS GPU.
Stripping .brres files avoids exhausting Kinoko's 16 MiB root heap on large custom courses.
"""
import io
import os
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'vendor/gclib'))
from unpack_szs import unpack

def pack_u8(root_dir: Path) -> bytes:
    nodes = []
    def walk(d: Path, parent_idx: int):
        node_idx = len(nodes)
        nodes.append({'is_dir': True, 'name': d.name if parent_idx != -1 else '', 'parent': max(0, parent_idx), 'next': 0, 'data': None})
        children = sorted(list(d.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
        for child in children:
            if child.is_dir():
                walk(child, node_idx)
            else:
                nodes.append({'is_dir': False, 'name': child.name, 'parent': 0, 'next': 0, 'data': child.read_bytes()})
        nodes[node_idx]['next'] = len(nodes)

    walk(root_dir, -1)
    nodes[0]['name'] = ''

    str_table = bytearray(b'\x00')
    str_offsets = []
    for n in nodes:
        if not n['name']:
            str_offsets.append(0)
        else:
            off = len(str_table)
            str_table.extend(n['name'].encode('latin1') + b'\x00')
            str_offsets.append(off)

    node_count = len(nodes)
    header_size = node_count * 12 + len(str_table)
    data_offset = (0x20 + header_size + 0x1f) & ~0x1f

    curr_data_off = data_offset
    for n in nodes:
        if not n['is_dir']:
            n['data_off'] = curr_data_off
            curr_data_off = (curr_data_off + len(n['data']) + 0x1f) & ~0x1f

    u8 = bytearray(0x20)
    struct.pack_into('>4sIII16s', u8, 0, b'U\xaa8-', 0x20, header_size, data_offset, b'\x00'*16)

    for i, n in enumerate(nodes):
        type_and_name = (0x01000000 if n['is_dir'] else 0x00000000) | (str_offsets[i] & 0x00FFFFFF)
        if n['is_dir']:
            u8.extend(struct.pack('>III', type_and_name, n['parent'], n['next']))
        else:
            u8.extend(struct.pack('>III', type_and_name, n['data_off'], len(n['data'])))

    u8.extend(str_table)
    if len(u8) < data_offset:
        u8.extend(b'\x00' * (data_offset - len(u8)))

    for n in nodes:
        if not n['is_dir']:
            if len(u8) < n['data_off']:
                u8.extend(b'\x00' * (n['data_off'] - len(u8)))
            u8.extend(n['data'])
            padded_len = (len(u8) + 0x1f) & ~0x1f
            u8.extend(b'\x00' * (padded_len - len(u8)))

    return bytes(u8)

def yaz0_fast_encode(data: bytes) -> bytes:
    out = bytearray(b'Yaz0')
    out.extend(struct.pack('>I8s', len(data), b'\x00'*8))
    i = 0
    n = len(data)
    while i < n:
        chunk = data[i : i + 8]
        bits = 0
        for b_idx in range(len(chunk)):
            bits |= (1 << (7 - b_idx))
        out.append(bits)
        out.extend(chunk)
        i += 8
    return bytes(out)

def optimize_szs(szs_path: Path, work_dir: Path):
    temp_dir = work_dir / szs_path.stem
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    unpack(szs_path, temp_dir)
    
    # Remove files never read by Kinoko:
    # All .brres (visual 3D models), .cobj, .rgrp (Wii-specific collision rules), DemoCol.kcl
    removed = 0
    saved_bytes = 0
    for p in list(temp_dir.rglob('*')):
        if p.is_file():
            name_lower = p.name.lower()
            if name_lower.endswith('.brres') or name_lower.endswith('.cobj') or name_lower.endswith('.rgrp') or name_lower == 'democol.kcl':
                saved_bytes += p.stat().st_size
                p.unlink()
                removed += 1
                
    # Also clean up empty subdirectories
    for d in sorted(list(temp_dir.rglob('*')), key=lambda p: len(str(p)), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            
    if removed > 0:
        raw_u8 = pack_u8(temp_dir)
        compressed = yaz0_fast_encode(raw_u8)
        szs_path.write_bytes(compressed)
        print(f"[+] Optimized {szs_path.name}: removed {removed} files ({saved_bytes/(1024*1024):.2f} MB), new size: {len(compressed)/(1024*1024):.2f} MB (decompressed: {len(raw_u8)/(1024*1024):.2f} MB)")
    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    scratch = ROOT / 'build/scratch_szs_opt'
    scratch.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        targets = [Path(p) for p in sys.argv[1:]]
    else:
        targets = []
        for base in [ROOT / 'sd-card/3ds/mkw-3ds/Race/Course', ROOT / 'build/release/sd-card/3ds/mkw-3ds/Race/Course']:
            if base.exists():
                for f in sorted(base.glob('*.szs')):
                    targets.append(f)
    for t in targets:
        optimize_szs(t, scratch)
