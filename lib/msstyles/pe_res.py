"""Read the resources of a PE file and write a resource-only PE32+ DLL.

Resources are a dict {type: {name: {language: bytes}}}; type and name are ints (IDs) or
upper-case strings, as Windows compares resource names case-insensitively.
"""
import struct

RT_BITMAP, RT_STRING = 2, 6


def _sections(data):
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<H', data, pe + 6)[0], struct.unpack_from('<H', data, pe + 20)[0]
    magic = struct.unpack_from('<H', data, pe + 24)[0]
    dirs = pe + 24 + (112 if magic == 0x20b else 96)
    secs = [struct.unpack_from('<IIII', data, pe + 24 + optsz + i * 40 + 8) for i in range(nsec)]
    return dirs, secs


def read(path):
    with open(path, 'rb') as f:
        data = f.read()
    dirs, secs = _sections(data)
    rva = struct.unpack_from('<I', data, dirs + 2 * 8)[0]

    def off(r):
        for vsize, va, rsize, roff in secs:
            if va <= r < va + max(vsize, rsize):
                return roff + r - va
        raise ValueError(f'RVA {r:#x} outside sections')
    root = off(rva)

    def name(n):
        if not n & 0x80000000:
            return n
        o = root + (n & 0x7fffffff)
        length = struct.unpack_from('<H', data, o)[0]
        return data[o + 2:o + 2 + 2 * length].decode('utf-16-le').upper()

    def entries(o):
        named, ids = struct.unpack_from('<HH', data, o + 12)
        for i in range(named + ids):
            yield struct.unpack_from('<II', data, o + 16 + 8 * i)

    out = {}
    for t, tdir in entries(root):
        for n, ndir in entries(root + (tdir & 0x7fffffff)):
            for lang, leaf in entries(root + (ndir & 0x7fffffff)):
                drva, size = struct.unpack_from('<II', data, root + leaf)
                out.setdefault(name(t), {}).setdefault(name(n), {})[lang] = data[off(drva):off(drva) + size]
    return out


def _order(keys):
    """Named entries first (sorted), then IDs ascending, as the format requires."""
    return sorted((k for k in keys if isinstance(k, str))) + sorted(k for k in keys if isinstance(k, int))


def _rsrc(res, section_rva):
    """Serialise the resource tree: directories, names, data entries, then data."""
    tables, strings, entries, blobs = [], {}, [], []
    # Lay out directory tables breadth-first: root, type dirs, name dirs.
    layout = [('root', None, None)]
    for t in _order(res):
        layout.append(('type', t, None))
    for t in _order(res):
        for n in _order(res[t]):
            layout.append(('name', t, n))
    offsets, pos = {}, 0
    for kind, t, n in layout:
        count = len(res) if kind == 'root' else len(res[t]) if kind == 'type' else len(res[t][n])
        offsets[(kind, t, n)] = pos
        pos += 16 + 8 * count
    for t in res:
        for n in res[t]:
            for key in (t, n):
                if isinstance(key, str) and key not in strings:
                    strings[key] = pos
                    pos += 2 + 2 * len(key)
    pos = (pos + 3) & ~3
    leaf_pos = {}
    for t in _order(res):
        for n in _order(res[t]):
            for lang in sorted(res[t][n]):
                leaf_pos[(t, n, lang)] = pos
                pos += 16
    data_pos = {}
    for key in leaf_pos:
        pos = (pos + 7) & ~7
        data_pos[key] = pos
        pos += len(res[key[0]][key[1]][key[2]])
    buf = bytearray(pos)

    def table(at, keys, target):
        named = sum(isinstance(k, str) for k in keys)
        struct.pack_into('<IIHHHH', buf, at, 0, 0, 0, 0, named, len(keys) - named)
        for i, k in enumerate(keys):
            ident = (0x80000000 | strings[k]) if isinstance(k, str) else k
            struct.pack_into('<II', buf, at + 16 + 8 * i, ident, target(k))
    table(0, _order(res), lambda t: 0x80000000 | offsets[('type', t, None)])
    for t in res:
        table(offsets[('type', t, None)], _order(res[t]), lambda n, t=t: 0x80000000 | offsets[('name', t, n)])
        for n in res[t]:
            table(offsets[('name', t, n)], sorted(res[t][n]), lambda lang, t=t, n=n: leaf_pos[(t, n, lang)])
    for s, at in strings.items():
        enc = s.encode('utf-16-le')
        struct.pack_into('<H', buf, at, len(s))
        buf[at + 2:at + 2 + len(enc)] = enc
    for key, at in leaf_pos.items():
        blob = res[key[0]][key[1]][key[2]]
        struct.pack_into('<IIII', buf, at, section_rva + data_pos[key], len(blob), 0, 0)
        buf[data_pos[key]:data_pos[key] + len(blob)] = blob
    return bytes(buf)


def write(path, res):
    """Write RES as a resource-only x86-64 DLL (what LoadLibraryEx(AS_DATAFILE) needs)."""
    file_align, sect_align, rva, headers = 0x200, 0x1000, 0x1000, 0x400
    rsrc = _rsrc(res, rva)
    raw = (len(rsrc) + file_align - 1) & ~(file_align - 1)
    image = rva + ((len(rsrc) + sect_align - 1) & ~(sect_align - 1))
    out = bytearray(headers)
    out[0:2] = b'MZ'
    struct.pack_into('<I', out, 0x3c, 0x40)
    out[0x40:0x44] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', out, 0x44, 0x8664, 1, 0, 0, 0, 240, 0x2022)
    opt = 0x58
    struct.pack_into('<HBBIIIII', out, opt, 0x20b, 14, 0, 0, raw, 0, 0, 0)
    struct.pack_into('<QIIHHHHHHIIIIHHQQQQII', out, opt + 24, 0x180000000, sect_align, file_align,
                     6, 0, 0, 0, 6, 0, 0, image, headers, 0, 3, 0x160, 0x100000, 0x1000,
                     0x100000, 0x1000, 0, 16)
    struct.pack_into('<II', out, opt + 112 + 2 * 8, rva, len(rsrc))
    sec = opt + 240
    out[sec:sec + 8] = b'.rsrc\0\0\0'
    struct.pack_into('<IIIIIIHHI', out, sec + 8, len(rsrc), rva, raw, headers, 0, 0, 0, 0, 0x40000040)
    with open(path, 'wb') as f:
        f.write(out + rsrc + bytes(raw - len(rsrc)))
