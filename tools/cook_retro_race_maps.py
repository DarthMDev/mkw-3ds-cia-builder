#!/usr/bin/env python3
"""Cook top-down minimaps and overviews for all retro/custom tracks in pulsar_manifest.json.

Uses the same pipeline as vanilla courses (tools/race_map_bake.py):
1. Reads course.kcl and course.kmp from the track's .szs archive.
2. Computes the orthographic top-down course frame and camera bounds.
3. Renders the course top-down using its cooked GMDL meshes, textures, and lighting,
   removing roofs/tunnels using KCL collision clearance.
4. Encodes 1024x1024 map and 256x256 overview textures into native 3DS ETC1 (.t3x).
5. Computes start line endpoints (CKPT 0 across road) and unitsPerPixel scale.
6. Stores the minimap metadata directly into pulsar_manifest.json.
"""

import argparse
import concurrent.futures
import io
import json
import math
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'vendor/gclib'))
import race_map_bake as rb
from devkitpro import tool
from gclib.yaz0_yay0 import Yaz0

def parse_kmp(b):
    if b[:4] != b'RKMD' or len(b) < 16:
        raise ValueError('Invalid KMP')
    size, n, h = struct.unpack_from('>IHH', b, 4)
    if size != len(b) or h < 16 + 4 * n:
        raise ValueError('Invalid KMP header')
    offsets = [h + struct.unpack_from('>I', b, 16 + 4 * i)[0] for i in range(n)] + [size]
    if offsets != sorted(offsets) or offsets[-2] + 8 > size:
        raise ValueError('Invalid KMP offsets')
    result = {}
    strides = {'KTPT': 28, 'ENPT': 20, 'ENPH': 16, 'ITPT': 20, 'ITPH': 16, 'CKPT': 20, 'CKPH': 16,
               'GOBJ': 60, 'AREA': 48, 'CAME': 72, 'JGPT': 28, 'CNPT': 28, 'MSPT': 28, 'STGI': 12}
    for start, end in zip(offsets, offsets[1:]):
        tag = b[start:start + 4].decode('ascii', errors='replace')
        count, extra = struct.unpack_from('>HH', b, start + 4)
        body = b[start + 8:end]
        section = {'count': count, 'header_extra': extra, 'offset': start, 'bytes': end - start}
        records = []
        if tag in strides:
            stride = strides[tag]
            if len(body) >= count * stride:
                for i in range(count):
                    raw = body[i * stride:(i + 1) * stride]
                    r = {'index': i}
                    if tag in ('ENPT', 'ITPT'):
                        r.update(position=struct.unpack_from('>3f', raw), width=struct.unpack_from('>f', raw, 12)[0])
                    elif tag in ('KTPT', 'JGPT', 'CNPT', 'MSPT'):
                        r.update(position=struct.unpack_from('>3f', raw), rotation=struct.unpack_from('>3f', raw, 12))
                    elif tag == 'CKPT':
                        r.update(left=struct.unpack_from('>2f', raw), right=struct.unpack_from('>2f', raw, 8),
                                 respawn=raw[16], type=raw[17], previous=raw[18], next=raw[19])
                    records.append(r)
        section['records'] = records
        result[tag] = section
    return result


def parse_kcl(b):
    pos_off, nrm_off, prism_off, block_off = struct.unpack_from('>4I', b, 0)
    positions = np.frombuffer(b, '>f4', count=(nrm_off - pos_off) // 4, offset=pos_off).reshape(-1, 3).astype(np.float64)
    normals = np.frombuffer(b, '>f4', count=(prism_off + 0x10 - nrm_off) // 4, offset=nrm_off)
    normals = normals[:len(normals) // 3 * 3].reshape(-1, 3).astype(np.float64)
    count = (block_off - prism_off - 0x10) // 0x10
    prisms = np.frombuffer(b, np.dtype([('h', '>f4'), ('p', '>u2'), ('f', '>u2'), ('e1', '>u2'), ('e2', '>u2'),
                                        ('e3', '>u2'), ('a', '>u2')]), count=count, offset=prism_off + 0x10)
    a = positions[prisms['p']]
    face = normals[prisms['f']]
    cross_a = np.cross(normals[prisms['e1']], face)
    cross_b = np.cross(normals[prisms['e2']], face)
    e3 = normals[prisms['e3']]
    h = prisms['h'].astype(np.float64)[:, None]
    with np.errstate(divide='ignore', invalid='ignore'):
        bpt = a + cross_b * (h / np.sum(cross_b * e3, axis=1, keepdims=True))
        cpt = a + cross_a * (h / np.sum(cross_a * e3, axis=1, keepdims=True))
    ok = np.isfinite(bpt).all(axis=1) & np.isfinite(cpt).all(axis=1)
    return a[ok], bpt[ok], cpt[ok], (prisms['a'][ok] & 0x1f).astype(np.int64), face[ok]

TEX3DS = str(tool('tex3ds'))
SD = ROOT / 'sd-card/3ds/mkw-3ds'
PLAYABLE = ROOT / 'build/playable/3ds/mkw-3ds'

UNITS_PER_PIXEL = 64.0
MAX_UNITS_PER_PIXEL = 110.0
OVERVIEW = 256


def extract_kcl_kmp(szs_bytes):
    """Decompress Yaz0/U8 archive in memory and return (kcl_bytes, kmp_bytes)."""
    if szs_bytes[:4] == b'Yaz0':
        szs_bytes = Yaz0.decompress(io.BytesIO(szs_bytes)).getvalue()
    if szs_bytes[:4] != b'U\xaa8-':
        return None, None
    root = struct.unpack_from('>I', szs_bytes, 4)[0]
    count = struct.unpack_from('>I', szs_bytes, root + 8)[0]
    strings = root + count * 12
    kcl_data = None
    kmp_data = None
    for i in range(1, count):
        info, offset, size = struct.unpack_from('>III', szs_bytes, root + i * 12)
        start = strings + (info & 0xffffff)
        name = szs_bytes[start:szs_bytes.index(0, start)].decode('ascii', errors='replace')
        if name == 'course.kcl':
            kcl_data = szs_bytes[offset:offset + size]
        elif name == 'course.kmp':
            kmp_data = szs_bytes[offset:offset + size]
    return kcl_data, kmp_data


def get_default_lighting():
    """Default bright daytime lighting for tracks without authored lighting."""
    try:
        return rb.course_lighting('Race/Course/beginner_course.szs')
    except Exception:
        lights = [(1601, 2, (0.7, 0.5, 0.4), 0x808078ff)]
        ambient = [0x6e6e6eff] * 16
        return lights, ambient


def bake_single_track(track_idx, track_name, arch_rel, model_list_name, out_dir):
    """Cooks a single track's minimap and overview."""
    szs_file = SD / arch_rel
    if not szs_file.is_file():
        return None, f"Archive not found: {arch_rel}"

    kcl_data, kmp_data = extract_kcl_kmp(szs_file.read_bytes())
    if not kcl_data or not kmp_data:
        return None, f"Missing KCL/KMP in archive: {arch_rel}"

    try:
        kmp = parse_kmp(kmp_data)
        kcl = parse_kcl(kcl_data)
    except Exception as e:
        return None, f"Failed parsing KCL/KMP for {track_name}: {e}"

    try:
        frame_rect, size = rb.course_frame(kmp)
    except Exception as e:
        return None, f"Failed computing course_frame for {track_name}: {e}"

    clean_model_list = model_list_name.replace('models/', '').replace('.list', '')
    list_path = SD / f'models/{clean_model_list}.list'
    if not list_path.is_file():
        return None, f"Model list not found: {list_path}"

    part_names = list_path.read_text().split()
    parts = []
    for pn in part_names:
        gmdl_path = SD / f'models/{pn}.gmdl'
        if gmdl_path.is_file():
            parts.append(rb.Part(gmdl_path))

    if not parts:
        return None, f"No model parts found for {track_name}"

    # Setup top-down rendering
    x0, z0, x1, z1 = frame_rect
    frame = rb.Frame(x0, z0, x1, z1, size[0] * 2, size[1] * 2)
    road, ground = rb.floor_maps(kcl, frame)
    ceiling = rb.ceiling_map(road, ground, frame)
    lights, ambient = get_default_lighting()
    background = np.array([0.10, 0.13, 0.18])

    try:
        colour, depth = rb.render(parts, frame, ceiling, lights, ambient, background)
        ground_height = np.median(ground[np.isfinite(ground)]) if np.isfinite(ground).any() else 0.0
        image = rb.finish(colour, depth, frame, background, ground_height)
        full = Image.fromarray((np.clip(image, 0, 1) * 255 + 0.5).astype(np.uint8))
        out_img = full.resize(size, Image.Resampling.BOX)
    except Exception as e:
        return None, f"Rendering failed for {track_name}: {e}"

    # File paths
    tex_base = f"race_map_retro_{track_idx:03d}"
    map_png = out_dir / 'textures' / f"{tex_base}.png"
    map_t3x = out_dir / 'textures' / f"{tex_base}.t3x"
    overview_png = out_dir / 'textures' / f"{tex_base}_overview.png"
    overview_t3x = out_dir / 'textures' / f"{tex_base}_overview.t3x"

    map_png.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(map_png)
    subprocess.run([TEX3DS, '-f', 'etc1', '-q', 'high', '-z', 'none', '-o', str(map_t3x), str(map_png)],
                   check=True, stdout=subprocess.DEVNULL)

    small = (OVERVIEW, OVERVIEW * size[1] // size[0]) if size[0] >= size[1] else (OVERVIEW * size[0] // size[1], OVERVIEW)
    out_img.resize(small, Image.Resampling.LANCZOS).save(overview_png)
    subprocess.run([TEX3DS, '-f', 'etc1', '-q', 'high', '-z', 'none', '-o', str(overview_t3x), str(overview_png)],
                   check=True, stdout=subprocess.DEVNULL)

    texel = (frame_rect[2] - frame_rect[0]) / size[0]
    view = min(max(UNITS_PER_PIXEL, 0.85 * texel), MAX_UNITS_PER_PIXEL)

    start = kmp['CKPT']['records'][0]
    start_pos = kmp['KTPT']['records'][0]['position'] if kmp.get('KTPT', {}).get('records') else [0.0, 0.0, 0.0]
    start_left, start_right = rb.road_span(kcl, start['left'], start['right'], start_pos)

    minimap_data = {
        'texture': f"textures/{tex_base}.t3x",
        'overview': f"textures/{tex_base}_overview.t3x",
        'frame': [round(float(v), 3) for v in frame_rect],
        'size': list(size),
        'overviewSize': list(small),
        'unitsPerPixel': round(float(view), 4),
        'startLeft': [round(float(start_left[0]), 3), round(float(start_left[1]), 3)],
        'startRight': [round(float(start_right[0]), 3), round(float(start_right[1]), 3)]
    }
    return minimap_data, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--force', action='store_true', help='Re-bake already cooked maps')
    args = parser.parse_args()

    manifest_file = SD / 'pulsar_manifest.json'
    manifest = json.loads(manifest_file.read_text())

    tasks = []
    global_idx = 0
    for cup_idx, cup in enumerate(manifest['cups']):
        for track_idx, track in enumerate(cup['tracks']):
            tex_base = f"race_map_retro_{global_idx:03d}"
            map_t3x = SD / 'textures' / f"{tex_base}.t3x"
            overview_t3x = SD / 'textures' / f"{tex_base}_overview.t3x"
            needs_bake = args.force or not map_t3x.is_file() or not overview_t3x.is_file() or 'minimap' not in track
            tasks.append({
                'global_idx': global_idx,
                'cup_idx': cup_idx,
                'track_idx': track_idx,
                'name': track['name'],
                'archive': track['archive'],
                'models': track['models'],
                'needs_bake': needs_bake
            })
            global_idx += 1

    to_cook = [t for t in tasks if t['needs_bake']]
    print(f"Total retro tracks: {len(tasks)}, tracks to bake: {len(to_cook)}")

    results = {}
    if to_cook:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
            future_to_task = {
                pool.submit(bake_single_track, t['global_idx'], t['name'], t['archive'], t['models'], SD): t
                for t in to_cook
            }
            done_count = 0
            for future in concurrent.futures.as_completed(future_to_task):
                t = future_to_task[future]
                done_count += 1
                try:
                    data, err = future.result()
                    if err:
                        print(f"[{done_count}/{len(to_cook)}] WARN {t['name']}: {err}")
                    else:
                        results[t['global_idx']] = data
                        print(f"[{done_count}/{len(to_cook)}] OK {t['name']} ({data['size'][0]}x{data['size'][1]}, {data['unitsPerPixel']:.1f} u/px)")
                except Exception as e:
                    print(f"[{done_count}/{len(to_cook)}] FAIL {t['name']}: {e}")

    # Update manifest
    updated_count = 0
    for t in tasks:
        idx = t['global_idx']
        cup = manifest['cups'][t['cup_idx']]
        track = cup['tracks'][t['track_idx']]
        if idx in results:
            track['minimap'] = results[idx]
            updated_count += 1
        elif 'minimap' in track:
            # Already had it
            pass

    manifest_file.write_text(json.dumps(manifest, indent=2) + '\n')
    if (PLAYABLE / 'pulsar_manifest.json').is_file():
        (PLAYABLE / 'pulsar_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"Updated pulsar_manifest.json with {updated_count} new minimaps ({len(tasks)} total).")


if __name__ == '__main__':
    main()
