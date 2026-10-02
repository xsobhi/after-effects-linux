#!/usr/bin/env python3
"""Summarise stacksnap.exe samples: where a thread spends its time.

  profile_report.py SAMPLES DLL_DIR...

Frames like "dvaui+0x1234" are named after the nearest exported function of that DLL
(found in DLL_DIR...). Prints the busiest leaf functions, the Adobe functions that call
into Wine/Windows most, inclusive time per function and the most common stacks.
"""
import collections
import os
import re
import struct
import sys

SYSTEM = {'ntdll', 'kernel32', 'kernelbase', 'win32u', 'user32', 'gdi32', 'opengl32', 'ucrtbase',
          'msvcrt', 'ole32', 'combase', 'rpcrt4', 'gdiplus', 'imm32', 'uxtheme', 'comctl32',
          'd3d11', 'dxgi', 'd2d1', 'dwrite', 'advapi32', 'sechost', 'msvcp140', 'vcruntime140',
          'vcruntime140_1', 'shell32', 'shlwapi', 'oleaut32', 'winmm', 'dbghelp'}


def demangle(name):
    """'?Draw@View@ui@dvaui@@QEAAXXZ' -> 'dvaui::ui::View::Draw' (good enough to read)."""
    m = re.match(r'\?([^@?]+)@([^?]*?)@@', name)
    if not m:
        return name
    return '::'.join(reversed([p for p in m.group(2).split('@') if p])) + '::' + m.group(1)


def exports(path):
    with open(path, 'rb') as f:
        data = f.read()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<HH', data, pe + 6)[0], struct.unpack_from('<H', data, pe + 20)[0]
    magic = struct.unpack_from('<H', data, pe + 24)[0]
    rva, size = struct.unpack_from('<II', data, pe + 24 + (112 if magic == 0x20b else 96))
    secs = [struct.unpack_from('<IIII', data, pe + 24 + optsz + i * 40 + 8) for i in range(nsec)]

    def off(r):
        for vsize, va, rsize, roff in secs:
            if va <= r < va + max(vsize, rsize):
                return roff + r - va
        raise ValueError
    if not rva:
        return []
    e = off(rva)
    nnames, funcs, names, ords = struct.unpack_from('<IIII', data, e + 24)
    out = []
    for i in range(nnames):
        name_rva = struct.unpack_from('<I', data, off(names) + 4 * i)[0]
        ordinal = struct.unpack_from('<H', data, off(ords) + 2 * i)[0]
        func = struct.unpack_from('<I', data, off(funcs) + 4 * ordinal)[0]
        n = off(name_rva)
        out.append((func, data[n:data.index(b'\0', n)].decode('latin1')))
    return sorted(out)


class Resolver:
    def __init__(self, dirs):
        self.files, self.cache = {}, {}
        for d in dirs:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(('.dll', '.exe', '.aex', '.8bx', '.prm')):
                        self.files.setdefault(os.path.splitext(f)[0].lower(), os.path.join(root, f))

    def __call__(self, frame):
        m = re.fullmatch(r'([^+!]+)\+0x([0-9a-f]+)', frame)
        if not m:
            return frame
        mod, offset = m.group(1).lower(), int(m.group(2), 16)
        if mod not in self.cache:
            try:
                self.cache[mod] = exports(self.files[mod]) if mod in self.files else []
            except (OSError, ValueError, struct.error):
                self.cache[mod] = []
        best = None
        for rva, name in self.cache[mod]:
            if rva > offset:
                break
            best = (rva, name)
        if best and offset - best[0] < 0x20000:
            return f'{mod}!{demangle(best[1])}'
        return f'{mod}+0x{offset:x}'


def module(frame):
    return re.split(r'[+!]', frame)[0].lower()


def main(samples, dirs):
    resolve = Resolver(dirs)
    stacks = []
    with open(samples) as f:
        for line in f:
            parts = line.split(' ', 1)
            if len(parts) == 2 and parts[1].strip():
                stacks.append([resolve(fr) for fr in parts[1].strip().split(' < ')])
    total = len(stacks)
    print(f'{total} samples')
    if not total:
        return
    leaf = collections.Counter(s[0] for s in stacks)
    caller = collections.Counter(next((fr for fr in s if module(fr) not in SYSTEM), '?') for s in stacks)
    incl = collections.Counter(fr for s in stacks for fr in set(s))
    whole = collections.Counter(' < '.join(s[:8]) for s in stacks)
    for title, counter, n in (('leaf (where the thread is)', leaf, 15),
                              ('first app frame (who called into Wine)', caller, 15),
                              ('inclusive', incl, 30), ('stacks (top 8 frames)', whole, 8)):
        print(f'\n== {title}')
        for key, count in counter.most_common(n):
            print(f'{100 * count / total:5.1f}%  {key}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
