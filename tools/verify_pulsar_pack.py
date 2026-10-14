"""Validate locally cooked Pulsar assets before building or staging an RR package."""
import json
from pathlib import Path


def verify_pulsar_pack(assets):
    assets = Path(assets)
    manifest = assets / 'pulsar_manifest.json'
    if not manifest.is_file():
        raise ValueError('No cooked Retro Rewind pack found. Supply your Retro Rewind folder '
                         'at the pack prompt; the repository does not bundle track assets.')
    data = json.loads(manifest.read_text())
    cups = data.get('cups', [])
    if not cups or any(not cup.get('tracks') or len(cup['tracks']) > 4 for cup in cups):
        raise ValueError('Retro Rewind manifest must contain cups with 1 to 4 tracks')

    def require(relative):
        path = Path(relative)
        if not relative or path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid Retro Rewind asset path: ' + str(relative))
        source = assets / path
        if not source.is_file() or not source.stat().st_size:
            raise ValueError('Missing Retro Rewind asset: ' + str(relative) + '; re-import the pack')
        return source

    tracks = 0
    for cup in cups:
        for track in cup['tracks']:
            require(track.get('archive', ''))
            for key in ('models', 'sky'):
                relative = track.get(key, '')
                if key == 'sky' and not relative:
                    continue
                names = require(relative).read_text().split()
                if not names:
                    raise ValueError('Empty Retro Rewind model list: ' + relative)
                for name in names:
                    if any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in name):
                        raise ValueError('Invalid Retro Rewind model name: ' + name)
                    require('models/' + name + '.gmdl')
            tracks += 1
    return len(cups), tracks
