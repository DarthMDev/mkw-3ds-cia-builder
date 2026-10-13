"""Reject packs whose payloads no longer match the cooked menu assets."""
import struct
from pathlib import Path


def verify_menu_pack(root):
    root = Path(root)
    path = root / 'menu.pak'
    with path.open('rb') as archive:
        magic, count, names_size = struct.unpack('<4sII', archive.read(12))
        if magic != b'MPK1' or not count or count > 200000 or not names_size or names_size > 16 << 20:
            raise ValueError('Invalid menu.pak header')
        table = archive.read(count * 12)
        names = archive.read(names_size)
        length = path.stat().st_size
        for i in range(count):
            name_at, offset, size = struct.unpack_from('<III', table, i * 12)
            if name_at >= len(names) or offset + size > length:
                raise ValueError('Invalid menu.pak entry')
            name = names[name_at:names.index(0, name_at)].decode()
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Invalid menu.pak path')
            source = root / relative
            archive.seek(offset)
            if not source.is_file() or archive.read(size) != source.read_bytes():
                raise ValueError(f'menu.pak is stale: {name}; run tools/pack_menu_assets.py before packaging')
    return count
