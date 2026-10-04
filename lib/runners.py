#!/usr/bin/env python3
"""Find the Wine builds on this machine, for the installer's Wine page.

  runners.py [--json]

Each entry: name, version, source (where it came from), root (the directory holding
bin/wine, what ADOBE_WINE_RUNNER takes), installed, patched (this project's runner) and
default (the `wine` on PATH, i.e. the machine's default Wine).
"""
import glob
import json
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser('~')
PATCHED_VERSION = 'cachyos-11.0-20260703'
# (source, glob of directories holding bin/wine)
PLACES = [
    ('Steam', '~/.steam/steam/steamapps/common/Proton*/files'),
    ('Steam', '~/.steam/steam/steamapps/common/Proton*/dist'),
    ('Steam', '~/.local/share/Steam/steamapps/common/Proton*/files'),
    ('Steam', '/mnt/*/SteamLibrary/steamapps/common/Proton*/files'),
    ('Steam (custom)', '~/.steam/steam/compatibilitytools.d/*/files'),
    ('Steam (custom)', '~/.local/share/Steam/compatibilitytools.d/*/files'),
    ('Heroic', '~/.config/heroic/tools/proton/*/files'),
    ('Heroic', '~/.config/heroic/tools/wine/*'),
    ('Lutris', '~/.local/share/lutris/runners/wine/*'),
    ('Bottles', '~/.local/share/bottles/runners/*'),
    ('Bottles (Flatpak)', '~/.var/app/com.usebottles.bottles/data/bottles/runners/*'),
    ('PlayOnLinux', '~/.PlayOnLinux/wine/linux-amd64/*'),
]


def config():
    """The installer's saved settings (KEY="value" lines)."""
    path = os.path.join(os.environ.get('XDG_CONFIG_HOME', HOME + '/.config'), 'adobe-wine', 'config')
    values = {}
    try:
        with open(path) as f:
            for line in f:
                key, sep, value = line.strip().partition('=')
                if sep and not key.startswith('#'):
                    values[key] = value.strip('"\'')
    except OSError:
        pass
    return values


def version_of(root):
    """Version text from the build's own files (no need to run it)."""
    for name in ('version', '../version'):
        try:
            with open(os.path.join(root, name)) as f:
                text = f.read().split()
            return text[-1] if text else ''
        except OSError:
            pass
    try:                                    # plain Wine builds: ask the binary (no prefix needed)
        out = subprocess.run([os.path.join(root, 'bin', 'wine'), '--version'], capture_output=True,
                             text=True, timeout=5).stdout.strip()
        return out.replace('wine-', '')
    except (OSError, subprocess.TimeoutExpired):
        return ''


def label(root):
    parts = os.path.normpath(root).split(os.sep)
    return parts[-2] if parts[-1] in ('files', 'dist') else parts[-1]


def patched_runner(cfg):
    runner_dir = cfg.get('ADOBE_WINE_RUNNER_DIR') or HOME + '/.local/share/adobe-wine/runner'
    root = os.path.join(runner_dir, 'files')
    installed = os.path.isfile(os.path.join(runner_dir, 'version')) and \
        PATCHED_VERSION in open(os.path.join(runner_dir, 'version')).read()
    return {'name': 'Proton-CachyOS 11.0 with the Adobe fixes', 'version': PATCHED_VERSION,
            'source': 'this project', 'root': root, 'installed': installed, 'patched': True,
            'default': False}


def find():
    cfg = config()
    found = [patched_runner(cfg)]
    seen = {os.path.realpath(found[0]['root'])}
    system = shutil.which('wine') or shutil.which('wine64')
    if system:
        root = os.path.dirname(os.path.dirname(os.path.realpath(system)))
        if os.path.realpath(root) not in seen:
            seen.add(os.path.realpath(root))
            found.append({'name': 'System Wine', 'version': version_of(root), 'source': 'system package',
                          'root': root, 'installed': True, 'patched': False, 'default': True})
    for source, pattern in PLACES:
        for root in sorted(glob.glob(os.path.expanduser(pattern))):
            real = os.path.realpath(root)
            if real in seen or not os.access(os.path.join(root, 'bin', 'wine'), os.X_OK):
                continue
            seen.add(real)
            found.append({'name': label(root), 'version': version_of(root), 'source': source,
                          'root': root, 'installed': True, 'patched': False, 'default': False})
    current = cfg.get('ADOBE_WINE_RUNNER') or found[0]['root']
    for r in found:
        r['current'] = os.path.realpath(r['root']) == os.path.realpath(current)
    return found


if __name__ == '__main__':
    runners = find()
    if '--json' in sys.argv:
        print(json.dumps(runners, indent=1))
    else:
        for r in runners:
            tags = [t for t, on in (('patched', r['patched']), ('machine default', r['default']),
                                    ('in use', r['current']), ('not downloaded', not r['installed'])) if on]
            print(f"{r['name']} {r['version']} [{r['source']}] {', '.join(tags)}\n  {r['root']}")
