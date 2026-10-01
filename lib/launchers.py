#!/usr/bin/env python3
"""Create menu entries, start scripts and file associations for Adobe apps found by scan.py.

  launchers.py SCAN.json      (only genuine installs get launchers)
"""
import io
import json
import os
import re
import struct
import subprocess
import sys

HOME = os.path.expanduser('~')
DATA = os.environ.get('XDG_DATA_HOME', os.path.join(HOME, '.local', 'share'))
BIN = os.path.join(HOME, '.local', 'bin')
ICONS = os.path.join(DATA, 'icons', 'hicolor', '256x256', 'apps')
MIME = {'After Effects': ('application/x-adobe-aftereffects-project', 'After Effects project', ['*.aep', '*.aet'])}
WRAPPER = '''#!/usr/bin/env bash
# Start {name} ({version}) in its Wine prefix; Linux file paths become Windows paths.
exe={exe!r}
args=()
for a in "$@"; do
    if [[ -e "$a" ]]; then a=$(ADOBE_WINE_PREFIX={prefix!r} "$HOME/.local/bin/adobe-wine" winepath -w "$(readlink -f "$a")" 2>/dev/null); fi
    args+=("$a")
done
cd "$(dirname "$exe")"
ADOBE_WINE_PREFIX={prefix!r} exec "$HOME/.local/bin/adobe-wine" "$exe" "${{args[@]}}"
'''


def pe_resources(data):
    """Return {(type, id): bytes} for the PE resource tree (first language of each)."""
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<H', data, pe + 6)[0], struct.unpack_from('<H', data, pe + 20)[0]
    magic = struct.unpack_from('<H', data, pe + 24)[0]
    rva = struct.unpack_from('<I', data, pe + 24 + (112 if magic == 0x20b else 96) + 16)[0]
    sections = [struct.unpack_from('<8sIIII', data, pe + 24 + optsz + i * 40) for i in range(nsec)]
    def off(r):
        for _, vsize, va, rsize, roff in sections:
            if va <= r < va + max(vsize, rsize):
                return roff + r - va
    root, out = off(rva), {}
    def entries(o):
        named, ids = struct.unpack_from('<HH', data, o + 12)
        for i in range(named + ids):
            name, target = struct.unpack_from('<II', data, o + 16 + i * 8)
            yield name, target
    for rtype, t in entries(root):
        if not t & 0x80000000:
            continue
        for rid, n in entries(root + (t & 0x7fffffff)):
            if not n & 0x80000000:
                continue
            for _, leaf in entries(root + (n & 0x7fffffff)):
                drva, size = struct.unpack_from('<II', data, root + leaf)
                out[(rtype, rid)] = data[off(drva):off(drva) + size]
                break
    return out


def extract_icon(exe, dest_base):
    """Write the exe's main icon as .ico, plus a 256px .png when Pillow is available."""
    with open(exe, 'rb') as f:
        res = pe_resources(f.read())
    groups = sorted(k for k in res if k[0] == 14)
    if not groups:
        return None
    grp = res[groups[0]]
    count = struct.unpack_from('<H', grp, 4)[0]
    entries, images = [], []
    for i in range(count):
        w, h, colors, _, planes, bpp, size, icon_id = struct.unpack_from('<BBBBHHIH', grp, 6 + i * 14)
        image = res.get((3, icon_id), b'')
        entries.append((w, h, colors, planes, bpp, len(image)))
        images.append(image)
    offset = 6 + 16 * count
    ico = struct.pack('<HHH', 0, 1, count)
    for (w, h, colors, planes, bpp, size), image in zip(entries, images):
        ico += struct.pack('<BBBBHHII', w, h, colors, 0, planes, bpp, size, offset)
        offset += size
    ico += b''.join(images)
    with open(dest_base + '.ico', 'wb') as f:
        f.write(ico)
    try:
        from PIL import Image
        with Image.open(io.BytesIO(ico)) as im:
            im.size = max(im.info.get('sizes', [im.size]))
            im.convert('RGBA').resize((256, 256)).save(dest_base + '.png')
        return dest_base + '.png'
    except Exception:
        return dest_base + '.ico'


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def install(app):
    name = app['folder'].replace('Adobe ', '')                    # "After Effects 2020"
    script = os.path.join(BIN, slug(name))
    os.makedirs(BIN, exist_ok=True); os.makedirs(ICONS, exist_ok=True)
    with open(script, 'w') as f:
        f.write(WRAPPER.format(name=name, version=app['version'], exe=app['exe'], prefix=app['prefix']))
    os.chmod(script, 0o755)
    icon = extract_icon(app['exe'], os.path.join(ICONS, 'adobe-wine-' + slug(name))) or 'applications-multimedia'
    exe_class = os.path.splitext(os.path.basename(app['exe']))[0].replace(' ', '')
    mime = MIME.get(app['app'])
    entry = ['[Desktop Entry]', 'Type=Application', f'Name={name}',
             f"Comment=Adobe {app['app']} {app['version']} (Wine)", f'Exec="{script}" %F',
             f'Icon={icon}', 'Terminal=false', 'Categories=AudioVideo;Video;Graphics;',
             f'StartupWMClass=steam_app_{exe_class}', 'StartupNotify=true']
    if mime:
        entry.append(f'MimeType={mime[0]};')
    path = os.path.join(DATA, 'applications', f'adobe-wine-{slug(name)}.desktop')
    with open(path, 'w') as f:
        f.write('\n'.join(entry) + '\n')
    if mime:
        install_mime(*mime)
        subprocess.run(['xdg-mime', 'default', os.path.basename(path), mime[0]], check=False)
    print(f'  {name}: menu entry + {script}')


def install_mime(mtype, comment, globs):
    pkg = os.path.join(DATA, 'mime', 'packages')
    os.makedirs(pkg, exist_ok=True)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
           f'  <mime-type type="{mtype}">\n    <comment>{comment}</comment>\n'
           + ''.join(f'    <glob pattern="{g}"/>\n' for g in globs) + '  </mime-type>\n</mime-info>\n')
    with open(os.path.join(pkg, 'adobe-wine.xml'), 'w') as f:
        f.write(xml)
    subprocess.run(['update-mime-database', os.path.join(DATA, 'mime')], check=False)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        for app in json.load(f):
            if app['genuine']:
                install(app)
    subprocess.run(['update-desktop-database', os.path.join(DATA, 'applications')], check=False)
