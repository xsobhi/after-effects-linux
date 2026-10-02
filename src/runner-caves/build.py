#!/usr/bin/env python3
"""Assemble the mshtml.dll code caves and write lib/mshtml_caves.py (used by lib/patch_runner.py).

Usage: build.py X86_64_MSHTML_DLL I386_MSHTML_DLL
  The DLLs are Proton-CachyOS 11.0's lib/wine/{x86_64,i386}-windows/mshtml.dll (unpatched, or
  patched by an older patch_runner without these caves). Needs binutils (as, ld, objcopy, nm).

Each cave goes into the zero padding after the end of .text and the section's VirtualSize is
extended to cover it. The 64-bit cave functions also get unwind entries (.pdata/.xdata padding)
so exceptions and backtraces can unwind through them.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'lib', 'mshtml_caves.py')
HELPERS = ('dispex_get_chain_builtin_id', 'script_parse_event', 'dispex_prop_put')
ARCHS = {
    # hooks: (function, offset of the nsIDOMElement call in it, its bytes, cave entry point)
    'x86_64': dict(src='mshtml-onevent64.s', emul='elf_x86_64', as_flag='--64', prefix='', hooks=[
        ('HTMLElement_setAttribute', 0xe5, 'ff9080010000', 'set_hook'),          # SetAttribute
        ('HTMLElement_removeAttribute', 0x41d, 'ff9090010000', 'remove_hook'),   # RemoveAttribute
    ]),
    'i386': dict(src='mshtml-onevent32.s', emul='elf_i386', as_flag='--32', prefix='_', hooks=[
        ('_HTMLElement_setAttribute@28', 0xa7, 'ff92c0000000', 'set_hook'),
        ('_HTMLElement_removeAttribute@16', 0x2a6, 'ff92c8000000', 'remove_hook'),
    ]),
}
# x86_64 unwind data per cave function: (prolog bytes, UNWIND_INFO)
STUB_UNWIND = bytes([1, 4, 1, 0, 4, 0x42, 0, 0])            # sub rsp,0x28
UNWIND64 = {
    'set_hook': ('4883ec28', STUB_UNWIND),
    'remove_hook': ('4883ec28', STUB_UNWIND),
    # push rsi; push rdi; push rbx; sub rsp,0x90
    'set_handler': ('5657534881ec90000000',
                    bytes([1, 10, 5, 0, 10, 0x01, 0x12, 0, 3, 0x30, 2, 0x70, 1, 0x60, 0, 0])),
}


def pe_layout(data):
    e = struct.unpack_from('<I', data, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<H', data, e + 6)[0], struct.unpack_from('<H', data, e + 20)[0]
    opt = e + 24
    pe64 = struct.unpack_from('<H', data, opt)[0] == 0x20b
    base = struct.unpack_from('<Q', data, opt + 24)[0] if pe64 else struct.unpack_from('<I', data, opt + 28)[0]
    secs = {}
    for i in range(nsec):
        o = opt + optsz + 40 * i
        vsize, va, rawsz, rawptr = struct.unpack_from('<IIII', data, o + 8)
        secs[data[o:o + 8].rstrip(b'\0').decode()] = dict(hdr=o, vsize=vsize, va=va, rawsz=rawsz, raw=rawptr)
    return base, opt + (112 if pe64 else 96), secs


def symbols(path):
    out = subprocess.run(['nm', path], capture_output=True, text=True, check=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def assemble(arch, cave_va, syms):
    a = ARCHS[arch]
    with tempfile.TemporaryDirectory() as tmp:
        obj, elf, binf = (os.path.join(tmp, n) for n in ('c.o', 'c.elf', 'c.bin'))
        subprocess.run(['as', a['as_flag'], '-o', obj, os.path.join(HERE, a['src'])], check=True)
        defs = [f'--defsym={h}={syms[a["prefix"] + h]:#x}' for h in HELPERS]
        subprocess.run(['ld', '-m', a['emul'], f'-Ttext={cave_va:#x}', '-e', 'set_hook', *defs,
                        '-o', elf, obj], check=True)
        subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', elf, binf], check=True)
        labels = {k: v for k, v in symbols(elf).items() if k in ('set_hook', 'remove_hook', 'set_handler')}
        return open(binf, 'rb').read(), labels


def u32(v):
    return struct.pack('<I', v).hex()


def unwind_patches(data, ddir, secs, cave, cave_rva, labels):
    pdata, xdata = secs['.pdata'], secs['.xdata']
    exc_size = struct.unpack_from('<I', data, ddir + 3 * 8 + 4)[0]
    assert exc_size == pdata['vsize'] and xdata['vsize'] % 4 == 0
    assert struct.unpack_from('<I', data, pdata['raw'] + pdata['vsize'] - 12)[0] < cave_rva, 'pdata order'
    funcs = sorted(labels, key=labels.get)
    ends = [labels[f] for f in funcs[1:]] + [cave_rva + len(cave)]
    entries, infos = b'', b''
    for func, end in zip(funcs, ends):
        prolog, info = UNWIND64[func]
        start = labels[func] - cave_rva
        assert cave[start:start + len(prolog) // 2].hex() == prolog, f'{func}: prolog changed, fix UNWIND64'
        if info not in infos:
            infos += info
        info_rva = xdata['va'] + xdata['vsize'] + infos.index(info)
        entries += struct.pack('<III', labels[func], end, info_rva)
    assert pdata['vsize'] + len(entries) <= pdata['rawsz'] and xdata['vsize'] + len(infos) <= xdata['rawsz']
    return [
        (pdata['raw'] + pdata['vsize'], '00' * len(entries), entries.hex(), 'RUNTIME_FUNCTIONs'),
        (xdata['raw'] + xdata['vsize'], '00' * len(infos), infos.hex(), 'their UNWIND_INFO'),
        (pdata['hdr'] + 8, u32(pdata['vsize']), u32(pdata['vsize'] + len(entries)), '.pdata VirtualSize'),
        (xdata['hdr'] + 8, u32(xdata['vsize']), u32(xdata['vsize'] + len(infos)), '.xdata VirtualSize'),
        (ddir + 3 * 8 + 4, u32(exc_size), u32(exc_size + len(entries)), 'exception directory size'),
    ]


def build(arch, path):
    a, data = ARCHS[arch], open(path, 'rb').read()
    base, ddir, secs = pe_layout(data)
    syms = symbols(path)
    text = secs['.text']
    cave_rva = text['va'] + (text['vsize'] + 15 & ~15)
    cave, labels = assemble(arch, base + cave_rva, syms)
    labels = {k: v - base for k, v in labels.items()}          # -> RVAs
    cave_off = text['raw'] + cave_rva - text['va']
    assert cave_rva - text['va'] + len(cave) <= text['rawsz'], 'no room after .text'
    patches = []
    for func, off, old, label in a['hooks']:
        hook_rva = syms[func] - base + off
        rel = labels[label] - (hook_rva + 5)
        patches.append((text['raw'] + hook_rva - text['va'], old, 'e8' + struct.pack('<i', rel).hex() + '90',
                        f'{func.strip("_").split("@")[0]}: call {label}'))
    patches += [
        (cave_off, '00' * len(cave), cave.hex(), 'set_hook, remove_hook, set_handler (src/runner-caves)'),
        (text['hdr'] + 8, u32(text['vsize']), u32(cave_rva - text['va'] + len(cave)), '.text VirtualSize'),
    ]
    if arch == 'x86_64':
        patches += unwind_patches(data, ddir, secs, cave, cave_rva, labels)
    for off, old, _, what in patches:
        assert data[off:off + len(old) // 2].hex() == old, f'{arch} {what}: unexpected bytes at {off:#x}'
    return patches


def main(x64, x86):
    lines = ['"""Generated by src/runner-caves/build.py - do not edit."""', '',
             '# (file offset, original bytes, patched bytes) for mshtml.dll: "on<event>" attributes',
             '# set or removed by script set or clear the event handler (patches/0009).']
    for name, arch, path in (('ONEVENT64', 'x86_64', x64), ('ONEVENT32', 'i386', x86)):
        lines.append(f'{name} = [')
        for off, old, new, what in build(arch, path):
            old = f"'00' * {len(old) // 2}" if not old.strip('0') else repr(old)
            if len(new) > 64:
                lines.append(f'    # {what}')
                lines.append(f'    ({off:#x}, {old}, (')
                lines += [f'        {new[i:i + 64]!r}' for i in range(0, len(new), 64)]
                lines.append('    )),')
            else:
                line = f'    ({off:#x}, {old}, {new!r}),'
                lines.append(f'{line:<58}  # {what}')
        lines.append(']')
    with open(OUT, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', os.path.normpath(OUT))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
