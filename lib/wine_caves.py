"""Code-cave patches for the Proton-CachyOS 11.0 x86_64 crypt32.dll and explorer.exe.

crypt32 (patches/0012):

CryptBinaryToString(CRYPT_STRING_BASE64*) of a multiple of 48 bytes (the text ends with a
full 64-character line) added the line separator twice: in the loop after the full line
and again after the last block. The A version then had no room left for the NUL (callers
using strlen() sent stray bytes; Red Giant's licence client did, so the service could not
decrypt the request and AME/AE hung loading Trapcode plugins), the W version wrote past
the caller's buffer. Both now end with one separator, as on Windows.

The A encoder is inlined into BinaryToBase64A: its pad_bytes == 0 path (final separator
at 0x5654) jumps to a cave that skips the separator when i (edi) is a non-zero multiple of
64. encodeBase64W: the in-loop separator is skipped after the last block when no padding
follows (r8d = i, r10d = 4 * blocks, r12d = pad_bytes). The caves sit in .text's tail
padding (raw offset = RVA here) and .text's VirtualSize grows to cover them.

explorer (patches/0013): when the folder to open is a directory (also for /select,FILE),
wWinMain's jump to Wine's explorer window goes to a cave that runs
ShellExecuteW(winereveal.exe, selection or root) and exits; if that cannot be started,
Wine's window opens as before. winereveal.exe (src/reveal) shows the file in the desktop's
file manager. parameters_struct is at rbp+0x370: root at +0x374, selection at +0x57c.
"""

CRYPT32_64 = ('cf4a90326d7bc26cc96bdec4921ad13fb9738ba609a4646ff1bdd94c0828aaae', [
    # BinaryToBase64A: mov [rbp-0x20],r9; mov rcx,[rbp-0x18]  ->  jmp a_cave
    (0x5654, '4c894de0488b4de8', 'e947a00700909090'),
    # a_cave: if (!pad_bytes && i && !(i & 63)) { rbx = ptr; skip separator }
    #         else redo the two moved instructions and continue with the separator
    (0x7f6a0, '00' * 37, '837dd800751285ff740e40f6c73f75084c89cbe9d35ff8ff'
                         '4c894de0488b4de8e9975ff8ff'),
    # encodeBase64W: test r8b,0x3f; jne next_block  ->  jmp w_cave
    (0x72635, '41f6c03f0f8571ffffff', 'e996d000009090909090'),
    # w_cave: separator after a full line only if more blocks or padding follow
    (0x7f6d0, '00' * 33, '41f6c03f0f85d62effff4539d00f855c2fffff4585e40f85532fffffe9bf2effff'),
    (0x190, 'a0e60700', '00e70700'),           # .text VirtualSize 0x7e6a0 -> 0x7e700
])

EXPLORER_64 = ('53dd1a35e47d8565cac6fa2fe415279edd99bf7b4f7a59de78f4b29ee2e0287d', [
    (0xf262, '0f855cf7ffff', '0f8538590000'),  # wWinMain: root is a directory -> cave
    (0x14ba0, '00' * 104,                      # cave + L"winereveal.exe"
     '4c8d8d7c050000664183390075074c8d8d7403000031d231c94c8d052a000000'
     'c74424280100000048c744242000000000ff15190a00004883f820760831c9ff'
     '15fbcb0000e9da9dffff770069006e006500720065007600650061006c002e00'
     '6500780065000000'),
    (0x190, 'a03b0100', '103c0100'),           # .text VirtualSize 0x13ba0 -> 0x13c10
])
