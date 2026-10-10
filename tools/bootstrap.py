#!/usr/bin/env python3
"""Restore pinned public source dependencies; never fetch game files."""
import json, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
deps = json.loads((root / 'dependencies.json').read_text())

for name in ('kinoko', 'noclip', 'gclib', 'citro3d'):
    dest = root / 'vendor' / name
    entry = deps[name]
    if not dest.exists():
        subprocess.run(['git', 'clone', '--no-checkout', entry['url'], str(dest)], check=True)
        subprocess.run(['git', '-C', str(dest), 'checkout', '--detach', entry['commit']], check=True)
    else:
        actual = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != entry['commit']:
            raise SystemExit(f"{name}: unexpected revision {actual}; expected {entry['commit']}")

    patch_path = entry.get('patch', f'patches/kinoko-arm11.patch' if name == 'kinoko' else None)
    if patch_path:
        patch_file = root / patch_path
        if patch_file.is_file():
            check_applied = subprocess.run(['git', '-C', str(dest), 'apply', '--reverse', '--check', str(patch_file)], capture_output=True)
            if check_applied.returncode != 0:
                print(f"Applying {patch_file.name} to {name}...")
                subprocess.run(['git', '-C', str(dest), 'apply', str(patch_file)], check=True)

print('Source dependencies ready. Run npm ci and install requirements.txt into a project virtualenv.')
