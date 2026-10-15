#!/usr/bin/env python3
"""Pulsar-3DS pack ingestion pipeline: import Pulsar / Retro Rewind mod packs into MKWii-3DS.

Reads a Pulsar mod folder (containing Config.pul / ConfigRT.pul, Tracks/, and/or pulsar_manifest.json),
batch-converts track archives (.szs) into native PICA200 models/textures (.gmdl/.t3x),
and generates the bundled pulsar_manifest.json for the 3DS runtime.
"""
import argparse
import concurrent.futures
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'vendor/gclib'))

from unpack_szs import unpack
from cook_model import cook

def load_crc_name_maps(pack_path: Path):
    """Load CRC32 -> Track Name mapping from FolderToTrackName*.txt in Ghosts/."""
    mapping = {}
    ghosts_dir = pack_path / 'Ghosts'
    for txt in [ghosts_dir / 'FolderToTrackNameRT.txt', ghosts_dir / 'FolderToTrackNameCT.txt', ghosts_dir / 'FolderToTrackName.txt']:
        if txt.exists():
            for line in txt.read_text(encoding='utf-8', errors='ignore').splitlines():
                if '=' in line:
                    name_part, crc_part = line.split('=', 1)
                    clean_name = re.sub(r'\\c\{[^}]*\}', '', name_part).strip()
                    crc_hex = crc_part.strip().upper()
                    if crc_hex:
                        try:
                            crc_int = int(crc_hex, 16)
                            mapping[crc_int] = clean_name
                        except ValueError:
                            pass
    return mapping

RETRO_REWIND_CUP_NAMES = [
    "SNES Mushroom Cup",
    "SNES Flower Cup",
    "SNES Star Cup",
    "SNES Special Cup",
    "SNES Extra Cup",
    "N64 Mushroom Cup",
    "N64 Flower Cup",
    "N64 Star Cup",
    "N64 Special Cup",
    "GBA Mushroom Cup",
    "GBA Flower Cup",
    "GBA Lightning Cup",
    "GBA Star Cup",
    "GBA Special Cup",
    "GCN Mushroom Cup",
    "GCN Flower Cup",
    "GCN Star Cup",
    "GCN Special Cup",
    "DS Mushroom Cup",
    "DS Flower Cup",
    "DS Star Cup",
    "DS Special Cup",
    "Wii Mushroom Cup",
    "Wii Flower Cup",
    "Wii Star Cup",
    "Wii Special Cup",
    "3DS Mushroom Cup",
    "3DS Flower Cup",
    "3DS Star Cup",
    "3DS Special Cup",
    "Wii U Mushroom Cup",
    "Wii U Flower Cup",
    "Wii U Star Cup",
    "Wii U Egg Cup",
    "Wii U Crossing Cup",
    "Tour Mushroom Cup",
    "Tour Flower Cup",
    "RMX Mushroom Cup",
    "RMX Flower Cup",
    "Arcade GP Cup",
    "Switch 2 Mushroom Cup",
    "Switch 2 Flower Cup",
    "Switch 2 Star Cup",
    "Bonus & Beta Cup",
]

def determine_track_laps(name: str, default_laps: int = 3) -> int:
    """Calculate authentic lap counts directly matching course.kmp STGI headers."""
    kmp_non_3 = {
        '3ds maka wuhu': 1,
        '3ds rainbow road': 1,
        '3ds wuhu loop': 1,
        'gba bowser castle 4': 2,
        'gcn baby park': 7,
        'gcn bowser\'s castle': 2,
        'gcn rainbow road': 2,
        'gcn wario colosseum': 2,
        'gp diamond city': 4,
        'n64 rainbow road': 2,
        'n64 wario stadium': 2,
        'snes choco island 1': 5,
        'snes ghost valley 1': 5,
        'snes koopa beach 1': 5,
        'snes mario circuit 1': 5,
        'snes vanilla lake 1': 5,
        'snes vanilla lake 2': 5,
        'sw2 dk spaceport': 1,
        'sw2 ghost valley': 2,
        'sw2 mario circuit': 1,
        'sw2 peach resort': 2,
        'sw2 rainbow road': 1,
        'tour athens dash': 1,
        'wii u big blue': 2,
    }
    return kmp_non_3.get(name.lower().strip(), default_laps)

def generate_cup_name(cup_idx: int, total_cups: int, first_track_name: str = ""):
    """Generate meaningful cup name based on Retro Rewind definitions or index."""
    if total_cups == 44 and cup_idx < len(RETRO_REWIND_CUP_NAMES):
        return RETRO_REWIND_CUP_NAMES[cup_idx]
    if cup_idx < len(RETRO_REWIND_CUP_NAMES):
        return RETRO_REWIND_CUP_NAMES[cup_idx]
    if first_track_name:
        for prefix in ("SNES", "N64", "GBA", "GCN", "DS", "Wii", "3DS", "Custom"):
            if prefix in first_track_name:
                return f"{prefix} Cup {cup_idx % 8 + 1}"
    return f"Retro Cup {cup_idx + 1}"

def parse_config_pul(data: bytes, crc_names: dict = None):
    """Parse binary Pulsar Config.pul / ConfigRT.pul file format."""
    if len(data) < 32 or data[:4] != b'PULS':
        raise ValueError("Invalid Config.pul magic header")

    magic, version, off_info, off_cups, off_bmg = struct.unpack_from('>4siiii', data, 0)
    mod_folder_raw = data[20:36]
    mod_folder = mod_folder_raw.split(b'\0', 1)[0].decode('ascii', errors='ignore').strip('/')

    info_dict = {}
    if off_info > 0 and off_info < len(data):
        info_magic, info_ver, info_sz = struct.unpack_from('>4sII', data, off_info)
        if info_magic == b'INFO':
            # Info payload starts after 12-byte section header
            room_key, prob100, prob150, wiimmfi_reg, track_block = struct.unpack_from('>IIIiI', data, off_info + 12)
            tt_trophies, has_200cc, has_umt, has_feather, has_mega_tc = struct.unpack_from('>5B', data, off_info + 32)
            info_dict = {
                'has_200cc': bool(has_200cc),
                'has_umt': bool(has_umt),
                'has_feather': bool(has_feather),
                'has_mega_tc': bool(has_mega_tc),
            }

    messages = {}
    if off_bmg > 0 and off_bmg < len(data):
        bmg_data = data[off_bmg:]
        if len(bmg_data) > 32 and bmg_data[:8] == b'MESGbmg1':
            pos = 32
            inf1 = mid1 = dat1 = None
            while pos < len(bmg_data):
                sec, size = struct.unpack_from('>4sI', bmg_data, pos)
                if sec == b'INF1': inf1 = bmg_data[pos:pos+size]
                elif sec == b'MID1': mid1 = bmg_data[pos:pos+size]
                elif sec == b'DAT1': dat1 = bmg_data[pos:pos+size]
                pos += size
            if inf1 and dat1:
                num_entries, entry_size = struct.unpack_from('>HH', inf1, 8)
                mids = []
                if mid1:
                    num_mids = struct.unpack_from('>H', mid1, 8)[0]
                    for i in range(num_mids):
                        mids.append(struct.unpack_from('>I', mid1, 16 + i * 4)[0])
                for i in range(num_entries):
                    offset = struct.unpack_from('>I', inf1, 16 + i * entry_size)[0]
                    str_start = 8 + offset
                    end = str_start
                    while end + 1 < len(dat1):
                        if dat1[end:end+2] == b'\x00\x00': break
                        end += 2
                    raw = dat1[str_start:end]
                    mid = mids[i] if i < len(mids) else i
                    messages[mid] = raw.decode('utf-16-be', errors='replace').strip()

    cups_list = []
    if off_cups > 0 and off_cups < len(data):
        cups_magic, cups_ver, cups_sz = struct.unpack_from('>4sII', data, off_cups)
        if cups_magic == b'CUPS':
            cts_cup_count, regs_mode = struct.unpack_from('>HB', data, off_cups + 12)
            track_stride = 8  # slot (1), musicSlot (1), variantCount (2), crc32 (4)
            offset = off_cups + 28  # offset in v3 after trophyCount (8 bytes) and totalVariantCount (4 bytes)
            global_track_idx = 0
            for cup_idx in range(cts_cup_count):
                tracks = []
                for t_idx in range(4):
                    if offset + track_stride <= len(data):
                        slot, music_slot, var_cnt, crc = struct.unpack_from('>BBHI', data, offset)
                        track_name = ""
                        if crc_names and crc in crc_names:
                            track_name = crc_names[crc]
                        else:
                            track_name = f"Track {global_track_idx + 1}"

                        tracks.append({
                            'name': track_name,
                            'slot': slot,
                            'music_slot': music_slot,
                            'crc32': crc,
                            'index': global_track_idx,
                            'author': messages.get(0x30000 + global_track_idx, ''),
                            'music_credit': messages.get(0x170000 + global_track_idx, '')
                        })
                        global_track_idx += 1
                        offset += track_stride

                first_name = tracks[0]['name'] if tracks else ""
                cup_name = generate_cup_name(cup_idx, cts_cup_count, first_name)
                cups_list.append({
                    'name': cup_name,
                    'tracks': tracks
                })

    return {
        'mod_name': mod_folder or "Retro Rewind",
        'info': info_dict,
        'cups': cups_list
    }

def convert_track(szs_path: Path, out_dir: Path, track_prefix: str, force: bool = False):
    """Unpack SZS and cook track geometry + sky into .gmdl lists."""
    build_export = ROOT / 'build/pulsar-exports' / track_prefix
    unpacked = build_export / 'unpacked'
    course_list_path = out_dir / 'models' / f'{track_prefix}.list'
    sky_list_path = out_dir / 'models' / f'{track_prefix}_sky.list'

    if not force and course_list_path.is_file() and course_list_path.stat().st_size > 0:
        return {
            'models': f'models/{track_prefix}.list',
            'sky': f'models/{track_prefix}_sky.list' if sky_list_path.is_file() and sky_list_path.read_text().strip() else ''
        }

    build_export.mkdir(parents=True, exist_ok=True)
    try:
        unpack(szs_path, unpacked)
    except Exception as e:
        print(f"[-] Failed to unpack {szs_path}: {e}")
        return {'models': '', 'sky': ''}

    # Export & cook course model
    course_brres = unpacked / 'course_model.brres'
    if not course_brres.exists():
        candidates = list(unpacked.glob('*course*.brres')) or list(unpacked.glob('*.brres'))
        if candidates:
            course_brres = candidates[0]

    if not course_brres.exists():
        print(f"[-] No course model BRRES found in {szs_path.name}")
        return {'models': '', 'sky': ''}

    exported_course = build_export / 'course'
    exported_course.mkdir(parents=True, exist_ok=True)
    export_env = {
        **os.environ,
        'MKW_FREEZE_NONLINEAR_UV': '1',
        'MKW_RETAIL_LIGHTING': '1',
        'MKW_COURSE_MATERIALS': '1'
    }

    exporter_bundle = ROOT / 'build/export_brres.mjs'
    if not exporter_bundle.exists():
        subprocess.run(['node', str(ROOT / 'tools/bundle_cooker.mjs')], cwd=ROOT, check=True)

    with (exported_course / 'export.log').open('w') as log:
        subprocess.run(
            ['node', str(exporter_bundle), str(course_brres), str(exported_course)],
            env=export_env, stdout=log, stderr=subprocess.STDOUT, check=True
        )

    cook(exported_course, out_dir, track_prefix, max_texture=256)

    # Export & cook sky model if present
    sky_brres = unpacked / 'vrcorn_model.brres'
    has_sky = False
    if sky_brres.exists():
        exported_sky = build_export / 'sky'
        exported_sky.mkdir(parents=True, exist_ok=True)
        sky_env = {**export_env, 'MKW_RETAIL_SKY': '1'}
        with (exported_sky / 'export.log').open('w') as log:
            subprocess.run(
                ['node', str(exporter_bundle), str(sky_brres), str(exported_sky)],
                env=sky_env, stdout=log, stderr=subprocess.STDOUT, check=True
            )
        sky_parts = cook(exported_sky, out_dir, f'{track_prefix}_sky', max_texture=256)
        has_sky = bool(sky_parts)

    return {
        'models': f'models/{track_prefix}.list',
        'sky': f'models/{track_prefix}_sky.list' if has_sky else ''
    }

def import_pack(pack_path: Path, out_dir: Path, config_file: str = None, max_cups: int = None, jobs: int = 4, force: bool = False):
    """Main pack ingestion routine."""
    print(f"[*] Ingesting Pulsar pack from {pack_path} -> {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'models').mkdir(parents=True, exist_ok=True)
    (out_dir / 'textures').mkdir(parents=True, exist_ok=True)
    (out_dir / 'Race/Course').mkdir(parents=True, exist_ok=True)

    crc_names = load_crc_name_maps(pack_path)
    if crc_names:
        print(f"[*] Loaded {len(crc_names)} track names from Ghosts folder")

    # Locate config file (ConfigRT.pul, ConfigCT.pul, or Config.pul)
    config_pul_path = None
    if config_file:
        candidate = pack_path / config_file if not (pack_path / 'Binaries' / config_file).exists() else pack_path / 'Binaries' / config_file
        if candidate.exists():
            config_pul_path = candidate
    if not config_pul_path:
        for candidate_name in ('ConfigRT.pul', 'ConfigCT.pul', 'Config.pul'):
            c1 = pack_path / 'Binaries' / candidate_name
            c2 = pack_path / candidate_name
            if c1.exists():
                config_pul_path = c1
                break
            elif c2.exists():
                config_pul_path = c2
                break

    manifest_json_path = pack_path / 'pulsar_manifest.json'
    tracks_dir = pack_path / 'Tracks'
    if not tracks_dir.exists():
        tracks_dir = pack_path

    mod_name = "Retro Rewind"
    has_200cc = True
    cups = []

    # Pre-index all SZS files in tracks directory by CRC32
    file_crcs = {}
    if tracks_dir.exists():
        print(f"[*] Pre-indexing SZS files in {tracks_dir} by CRC32...")
        for szs in tracks_dir.glob('*.szs'):
            try:
                c = zlib.crc32(szs.read_bytes()) & 0xffffffff
                file_crcs[c] = szs
            except Exception:
                pass
        print(f"[*] Indexed {len(file_crcs)} SZS files by CRC32")

    if config_pul_path and config_pul_path.exists():
        print(f"[*] Parsing Config binary at {config_pul_path}")
        parsed = parse_config_pul(config_pul_path.read_bytes(), crc_names)
        mod_name = parsed.get('mod_name', mod_name)
        has_200cc = parsed.get('info', {}).get('has_200cc', False)
        cups = parsed.get('cups', [])
    elif manifest_json_path.exists():
        print(f"[*] Loading existing manifest {manifest_json_path}")
        data = json.loads(manifest_json_path.read_text())
        mod_name = data.get('mod_name', mod_name)
        has_200cc = data.get('settings', {}).get('enable_200cc', False)
        cups = data.get('cups', [])
    else:
        print(f"[*] Auto-discovering SZS tracks in {tracks_dir}")
        all_szs = sorted(list(tracks_dir.glob('*.szs')))
        track_defs = []
        for i, szs in enumerate(all_szs):
            name = szs.stem.replace('_', ' ').title()
            track_defs.append({
                'name': name,
                'course_id': i % 32,
                'archive': f"Race/Course/{szs.name}",
                'szs_file': szs,
                'laps': 3,
                'music_stream_id': i % 32
            })
        for cup_idx in range((len(track_defs) + 3) // 4):
            cup_tracks = track_defs[cup_idx * 4 : (cup_idx + 1) * 4]
            cups.append({
                'name': f"Cup {cup_idx + 1}",
                'icon': f"cup_{cup_idx:02d}.t3x",
                'tracks': cup_tracks
            })

    if max_cups and max_cups > 0:
        cups = cups[:max_cups]
        print(f"[*] Limiting to first {len(cups)} cups as requested")

    # Prepare track list and conversion jobs
    conversion_tasks = []
    final_cups = []
    track_counter = 0

    for cup_idx, cup in enumerate(cups):
        new_tracks = []
        for track in cup.get('tracks', []):
            track_counter += 1
            t_name = track.get('name', f"Track {track_counter}")
            slot = track.get('course_id', track.get('slot', 0))
            archive = track.get('archive', '')
            t_idx = track.get('index', track_counter - 1)
            t_crc = track.get('crc32', 0)

            # Resolve local SZS file via CRC32, known mappings, or filenames
            szs_file = None
            if t_crc and t_crc in file_crcs:
                szs_file = file_crcs[t_crc]
            elif 'szs_file' in track and Path(track['szs_file']).exists():
                szs_file = Path(track['szs_file'])
            elif (tracks_dir / f"{t_idx}.szs").exists():
                szs_file = tracks_dir / f"{t_idx}.szs"
            elif archive:
                arch_name = Path(archive).name
                candidate = tracks_dir / arch_name
                if candidate.exists():
                    szs_file = candidate
            elif 'sunshine airport' in t_name.lower() and (tracks_dir / 'uSSA.szs').exists():
                szs_file = tracks_dir / 'uSSA.szs'
            if not szs_file:
                # Search by clean stem without loose substring matching
                clean_name = t_name.lower().replace(' ', '_').replace("'", '')
                for candidate in tracks_dir.glob('*.szs'):
                    if clean_name == candidate.stem.lower():
                        szs_file = candidate
                        break

            if not szs_file or not szs_file.is_file():
                raise ValueError(f'Missing source track archive for {t_name}; check the pack folder')

            prefix = f"pulsar_track_{track_counter:03d}"
            target_archive_rel = f"Race/Course/{szs_file.name if szs_file else f'{prefix}.szs'}"

            entry = {
                'name': t_name,
                'course_id': slot,
                'archive': target_archive_rel,
                'models': f"models/{prefix}.list",
                'sky': f"models/{prefix}_sky.list",
                'laps': determine_track_laps(t_name, track.get('laps', 3)),
                'music_stream_id': track.get('music_stream_id', track.get('music_slot', slot))
            }
            new_tracks.append(entry)

            if szs_file and szs_file.exists():
                target_szs = out_dir / target_archive_rel
                target_szs.parent.mkdir(parents=True, exist_ok=True)
                if not target_szs.exists() or force:
                    shutil.copy2(szs_file, target_szs)
                conversion_tasks.append((szs_file, out_dir, prefix, force))

        final_cups.append({
            'name': cup.get('name', f"Cup {cup_idx + 1}"),
            'icon': cup.get('icon', ''),
            'tracks': new_tracks
        })

    print(f"[*] Processing {len(conversion_tasks)} track model conversions across {jobs} workers...")
    if not conversion_tasks:
        raise ValueError('No tracks found in the supplied pack')
    entries = [track for cup in final_cups for track in cup['tracks']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = [executor.submit(convert_track, *task) for task in conversion_tasks]
        for entry, future in zip(entries, futures):
            result = future.result()
            if not result.get('models'):
                raise ValueError(f"Track conversion failed: {entry['name']}")
            entry.update(result)
    # Copy custom music streams from pack's strm/ directory if present
    pack_strm = pack_path / 'strm'
    if pack_strm.is_dir():
        out_strm = out_dir / 'audio/strm'
        out_strm.mkdir(parents=True, exist_ok=True)
        strm_copied = 0
        for bf in pack_strm.glob('*.brstm'):
            dest_bf = out_strm / bf.name
            if not dest_bf.is_file() or force:
                shutil.copy2(bf, dest_bf)
                strm_copied += 1
        print(f"[*] Copied {strm_copied} custom track music streams into {out_strm}")

    # Generate output manifest
    manifest_data = {
        'mod_name': mod_name,
        'version': "1.0",
        'cups': final_cups,
        'settings': {
            'enable_200cc': has_200cc,
            'brake_drifting': True,
            'hard_ai': False,
            'custom_items': True,
            'custom_items_bitfield': 524287,
            'default_engine_class': 3 if has_200cc else 2
        }
    }

    out_manifest = out_dir / 'pulsar_manifest.json'
    out_manifest.write_text(json.dumps(manifest_data, indent=2) + '\n')
    print(f"[+] Pack ingestion complete! Manifest written to {out_manifest}")
    print(f"[+] Total cups: {len(final_cups)}, Total tracks: {track_counter}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path, help="Path to Pulsar / Retro Rewind pack directory")
    parser.add_argument('--config', type=str, default=None, help="Specific Config.pul to parse (e.g. ConfigRT.pul)")
    parser.add_argument('--max-cups', type=int, default=None, help="Limit number of cups to import")
    parser.add_argument('--out', type=Path, default=ROOT / 'sd-card/3ds/mkw-3ds', help="Output directory")
    parser.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1), help="Worker threads")
    parser.add_argument('--force', action='store_true', help="Re-cook all tracks")
    args = parser.parse_args()

    if not args.pack.exists():
        raise SystemExit(f"Pack directory not found: {args.pack}")

    import_pack(args.pack, args.out, args.config, args.max_cups, args.jobs, args.force)

if __name__ == '__main__':
    main()
