#!/usr/bin/env python3
"""Pack race-time models, animation banks (incl. course-object .dobj) and textures into race.pak.

Same MPK1 format and rationale as tools/pack_menu_assets.py: loading a race
opens hundreds of small files (track parts, twelve racers, items and HUD), and
each open/close costs far more than its read. The selection is exactly the
validated package list from tools/package_sd.py, minus what menu.pak holds.
"""
import hashlib, json, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'sd-card/3ds/mkw-3ds'


def menu_pak_names():
    path = ASSETS / 'menu.pak'
    if not path.is_file():
        return set()
    data = path.read_bytes()
    count, names_bytes = struct.unpack_from('<II', data, 4)
    blob = data[12 + 12 * count:12 + 12 * count + names_bytes]
    return {n.decode() for n in blob.split(b'\0') if n}


def main():
    listing = json.loads(subprocess.check_output([sys.executable, str(ROOT / 'tools/package_sd.py'), '--list'], text=True))
    packed_menu = menu_pak_names()
    names = sorted(rel for rel in listing
                   if (rel.startswith('models/') and rel.endswith(('.gmdl', '.dskm', '.dobj')))
                   or (rel.startswith('textures/') and rel.endswith(('.t3x', '.bin'))))
    names = [n for n in names if n not in packed_menu]
    blob = b''.join(n.encode() + b'\0' for n in names)
    header = 12 + 12 * len(names) + len(blob)
    offset = (header + 31) & ~31
    entries = []
    output = ASSETS / 'race.pak'
    with output.open('wb') as out:
        sizes = [Path(listing[n]).stat().st_size for n in names]
        name_offset = 0
        for n, size in zip(names, sizes):
            entries.append((name_offset, offset, size))
            name_offset += len(n.encode()) + 1
            offset += (size + 31) & ~31
        if offset >= 1 << 31:
            raise SystemExit('race.pak exceeds the 2 GiB seek range')
        out.write(b'MPK1' + struct.pack('<II', len(names), len(blob)))
        for entry in entries:
            out.write(struct.pack('<III', *entry))
        out.write(blob)
        out.write(b'\0' * (((header + 31) & ~31) - header))
        for n, size in zip(names, sizes):
            data = Path(listing[n]).read_bytes()
            out.write(data + b'\0' * (((size + 31) & ~31) - size))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    receipt = {'version': 1, 'files': len(names), 'bytes': output.stat().st_size, 'sha256': digest}
    (ASSETS / 'models/race-pak.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(receipt, indent=1))


if __name__ == '__main__':
    main()
