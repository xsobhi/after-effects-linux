#!/usr/bin/env python3
"""Find Adobe After Effects / Media Encoder installs in Wine prefixes.

  scan.py [--json] [PREFIX...]     (no PREFIX: search the usual prefix locations)

For each install it reports the version and whether Adobe's key program files are
exactly as Adobe signed them (modified installs are not set up).
"""
import glob
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_adobe  # noqa: E402

HOME = os.path.expanduser('~')
SEARCH = [
    '~/.local/share/adobe-wine/prefix', '~/.wine', '~/.local/share/wineprefixes/*',
    '~/Games/*', '~/Games/*/*', '~/Games/Heroic/Prefixes/*/*', '~/.PlayOnLinux/wineprefix/*',
    '~/.local/share/bottles/bottles/*', '~/.var/app/com.usebottles.bottles/data/bottles/bottles/*',
    '~/.steam/steam/steamapps/compatdata/*/pfx', '~/.local/share/Steam/steamapps/compatdata/*/pfx',
    '/mnt/*/SteamLibrary/steamapps/compatdata/*/pfx',
]
APPS = [  # name, install-dir glob, main exe, extra files that cracks typically patch
    ('After Effects', 'Adobe After Effects *', 'Support Files/AfterFX.exe',
     ['Support Files/AfterFXLib.dll', 'Support Files/EAClient.dll', 'Support Files/SweetPeaSupport.dll']),
    ('Media Encoder', 'Adobe Media Encoder *', 'Adobe Media Encoder.exe',
     ['AMEFrontend.dll', 'EAClient.dll', 'SweetPeaSupport.dll']),
]
# Major version -> marketing year, and which combinations have been tested with this project.
LATER = {22: 2022, 23: 2023, 24: 2024, 25: 2025, 26: 2026}
YEARS = {'After Effects': {15: 2018, 16: 2019, 17: 2020, 18: 2021, **LATER},
         'Media Encoder': {12: 2018, 13: 2019, 14: 2020, 15: 2021, **LATER}}
TESTED = {('After Effects', 17): 'tested', ('Media Encoder', 14): 'in progress'}


def file_version(path):
    """FileVersion from the PE's VS_FIXEDFILEINFO block."""
    with open(path, 'rb') as f:
        data = f.read()
    i = data.find(struct.pack('<I', 0xFEEF04BD))
    if i < 0:
        return None
    ms, ls = struct.unpack_from('<II', data, i + 8)
    return f'{ms >> 16}.{ms & 0xffff}.{ls >> 16}.{ls & 0xffff}'


def prefixes(explicit):
    found = []
    for pattern in explicit or SEARCH:
        for path in glob.glob(os.path.expanduser(pattern)):
            path = os.path.realpath(path)
            if os.path.isfile(os.path.join(path, 'system.reg')) and os.path.isdir(os.path.join(path, 'drive_c')) \
                    and path not in found:
                found.append(path)
    return found


def scan(explicit=None):
    roots = verify_adobe.load_roots()
    results = []
    for prefix in prefixes(explicit):
        for name, pattern, exe, extra in APPS:
            for base in ('Program Files/Adobe', 'Program Files (x86)/Adobe'):
                for app_dir in sorted(glob.glob(os.path.join(prefix, 'drive_c', base, pattern))):
                    exe_path = os.path.join(app_dir, exe)
                    if not os.path.isfile(exe_path):
                        continue
                    version = file_version(exe_path) or '?'
                    major = int(version.split('.')[0]) if version[0].isdigit() else 0
                    checks = {p: verify_adobe.verify(os.path.join(app_dir, p), roots)
                              for p in [exe] + extra if os.path.isfile(os.path.join(app_dir, p))}
                    results.append({
                        'app': name, 'version': version, 'year': YEARS[name].get(major),
                        'folder': os.path.basename(app_dir), 'prefix': prefix, 'exe': exe_path,
                        'genuine': all(v == 'ok' for v in checks.values()),
                        'problems': {p: v for p, v in checks.items() if v != 'ok'},
                        'status': TESTED.get((name, major), 'experimental'),
                    })
    return results


def main(argv):
    as_json = '--json' in argv
    found = scan([a for a in argv if a != '--json'])
    if as_json:
        print(json.dumps(found, indent=1))
        return 0
    if not found:
        print('No After Effects or Media Encoder installs found in Wine prefixes.')
    for r in found:
        state = 'genuine' if r['genuine'] else 'MODIFIED: ' + ', '.join(r['problems'])
        print(f"{r['folder']} ({r['version']}, {r['status']}) - {state}\n  {r['prefix']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
