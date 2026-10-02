#!/usr/bin/env python3
"""Assemble the mshtml.dll code caves and write lib/mshtml_caves.py (used by lib/patch_runner.py).

Usage: build.py X86_64_MSHTML_DLL I386_MSHTML_DLL
  The DLLs are Proton-CachyOS 11.0's lib/wine/{x86_64,i386}-windows/mshtml.dll (unpatched, or
  patched by an older patch_runner without these caves). Needs binutils (as, ld, objcopy, nm).

Each cave goes into the zero padding after the end of .text and the section's VirtualSize is
extended to cover it. The 64-bit cave also gets an unwind entry (.pdata/.xdata padding) so
exceptions and backtraces can unwind through it.
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
    # hook: offset into HTMLElement_setAttribute of the nsIDOMElement_SetAttribute call
    'x86_64': dict(src='mshtml-onevent64.s', emul='elf_x86_64', as_flag='--64', prefix='',
                   hook_sym='HTMLElement_setAttribute', hook_off=0xe5, hook_old='ff9080010000'),
    'i386': dict(src='mshtml-onevent32.s', emul='elf_i386', as_flag='--32', prefix='_',
                 hook_sym='_HTMLElement_setAttribute@28', hook_off=0xa7, hook_old='ff92c0000000'),
}
# push rsi (1 byte); push rdi (1); sub rsp,0x98 (7) -> UNWIND_INFO v1, prolog 9, 4 code slots
UNWIND64 = bytes([1, 9, 4, 0, 9, 0x01, 0x13, 0, 2, 0x70, 1, 0x60])


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
        subprocess.run(['ld', '-m', a['emul'], f'-Ttext={cave_va:#x}', '-e', 'onevent', *defs,
                        '-o', elf, obj], check=True)
        subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', elf, binf], check=True)
        return open(binf, 'rb').read()


def u32(v):
    return struct.pack('<I', v).hex()


def build(arch, path):
    a, data = ARCHS[arch], open(path, 'rb').read()
    base, ddir, secs = pe_layout(data)
    syms = symbols(path)
    text = secs['.text']
    cave_rva = text['va'] + (text['vsize'] + 15 & ~15)
    cave = assemble(arch, base + cave_rva, syms)
    cave_off = text['raw'] + cave_rva - text['va']
    assert cave_rva - text['va'] + len(cave) <= text['rawsz'], 'no room after .text'
    hook_off = syms[a['hook_sym']] - base + a['hook_off'] - text['va'] + text['raw']
    rel = cave_rva - (hook_off - text['raw'] + text['va'] + 5)
    patches = [
        (hook_off, a['hook_old'], 'e8' + struct.pack('<i', rel).hex() + '90', 'SetAttribute -> onevent'),
        (cave_off, '00' * len(cave), cave.hex(), 'onevent (src/runner-caves)'),
        (text['hdr'] + 8, u32(text['vsize']), u32(cave_rva - text['va'] + len(cave)), '.text VirtualSize'),
    ]
    if arch == 'x86_64':
        pdata, xdata = secs['.pdata'], secs['.xdata']
        exc_size = struct.unpack_from('<I', data, ddir + 3 * 8 + 4)[0]
        assert exc_size == pdata['vsize'] and pdata['vsize'] + 12 <= pdata['rawsz']
        assert xdata['vsize'] % 4 == 0 and xdata['vsize'] + len(UNWIND64) <= xdata['rawsz']
        last_begin = struct.unpack_from('<I', data, pdata['raw'] + pdata['vsize'] - 12)[0]
        assert last_begin < cave_rva, 'pdata must stay sorted'
        unwind_rva = xdata['va'] + xdata['vsize']
        entry = struct.pack('<III', cave_rva, cave_rva + len(cave), unwind_rva)
        patches += [
            (pdata['raw'] + pdata['vsize'], '00' * 12, entry.hex(), 'RUNTIME_FUNCTION for onevent'),
            (xdata['raw'] + xdata['vsize'], '00' * len(UNWIND64), UNWIND64.hex(), 'its UNWIND_INFO'),
            (pdata['hdr'] + 8, u32(pdata['vsize']), u32(pdata['vsize'] + 12), '.pdata VirtualSize'),
            (xdata['hdr'] + 8, u32(xdata['vsize']), u32(xdata['vsize'] + len(UNWIND64)), '.xdata VirtualSize'),
            (ddir + 3 * 8 + 4, u32(exc_size), u32(exc_size + 12), 'exception directory size'),
        ]
    for off, old, _, what in patches:
        assert data[off:off + len(old) // 2].hex() == old, f'{arch} {what}: unexpected bytes at {off:#x}'
    return patches


def main(x64, x86):
    lines = ['"""Generated by src/runner-caves/build.py - do not edit."""', '',
             '# (file offset, original bytes, patched bytes) for mshtml.dll: "on<event>" attributes',
             '# set by setAttribute() get a working event handler (patches/0008).']
    for name, arch, path in (('ONEVENT64', 'x86_64', x64), ('ONEVENT32', 'i386', x86)):
        lines.append(f'{name} = [')
        for off, old, new, what in build(arch, path):
            if len(new) > 64:
                lines.append(f'    # {what}')
                lines.append(f'    ({off:#x}, {old[:2]!r} * {len(old) // 2}, (')
                lines += [f'        {new[i:i + 64]!r}' for i in range(0, len(new), 64)]
                lines.append('    )),')
            else:
                lines.append(f'    ({off:#x}, {old!r}, {new!r}),'.ljust(60) + f'# {what}')
        lines.append(']')
    with open(OUT, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', os.path.normpath(OUT))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
