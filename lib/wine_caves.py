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

win32u (patches/0014): move_window_bits copied a moved child window's whole old rectangle
within the parent's window surface, including what lay outside the parent (After Effects
scrolls its panel stacks by moving tall child windows: the timeline showed through the
Effects & Presets panel), and wineserver's exposure ignores the move offset, so nothing
repainted it. The cave clips the copy to the parent DC's clip box, invalidates the rest,
and records the time; flush_window_surfaces then skips idle flushes for 40 ms, so the app's
repaint lands before the frame is shown. Cave in the code segment's tail padding (the
segment grows), the timestamp just past .bss (the data segment's memsz grows).
src/runner-caves/win32u-move.s is the source (as --64; calls resolved to these offsets).
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

WIN32U_64 = ('cc68ef24f80d15ff4fc7df598910a1437b09f4a64dcca83594678dbebe75a1a8', [
    (0x100b40, '7440', 'eb40'),                # draw_menu_item: grayed text, no emboss
    (0x100bf4, '7424', 'eb24'),                # ... and its shortcut text
    (0x100c90, 'bf0e000000', 'bf07000000'),    # hot item text: COLOR_MENUTEXT
    (0x100ead, 'bf0d000000', 'bf1d000000'),    # hot item fill: COLOR_MENUHILIGHT
    (0xff6be, '8d5004', '8d5008'),             # calc_menu_item_size: row = text + 8
    (0x4f42c, '488b7db8488d75cc', 'e93fe41600909090'),  # move_window_bits -> move cave
    (0x4dea0, '554889e54155', 'e97bfb160090'),          # flush_window_surfaces -> flush cave
    (0x1bd870, '00' * 486,
     '4883ec40488b7db8be01000000e88e85feff4885c00f84840100004889442410'
     'e86bf2ffff483b4424100f846f010000488b7c241031f6ba02000000e85f10e9'
     'ff4885c00f845501000048894424184889c74889e6e88609e8ff89442430488b'
     '7c2410488b742418e81319e9ff837c2430000f8427010000895c242044897c24'
     '248b45b0894424288b45ac8944242c89d84429e04489f94429f1443b2424440f'
     '4c2424443b742404440f4c7424048b55a83b5424080f4f5424088b75b43b7424'
     '0c0f4f74240c4439e2410f4cd44439f6410f4cf68955a88975b4418d1c04458d'
     '3c0e8d3c02897db08d3c0e897dac3b5c2420751a443b7c242475133b7c242c75'
     '0d8b45b03b4424280f84910000008b7c24208b7424248b5424288b4c242ce81d'
     '3df8ff488944243089df4489fe8b55b08b4dace8083df8ff4889442438488b7c'
     '24304889fe4889c2b904000000e81e4ff8ff488b7c2430418b7510f7de418b55'
     '14f7dae88839f8ff488b7db831f6488b542430b985040000e88325e9ffe80e1d'
     'e7ff83c8018905550d0f00488b7c2430e86bf3f2ff488b7c2438e861f3f2ff48'
     '83c440488b7db8488d75cce9141ae9ff85ff74268b05260d0f0085c0741c57e8'
     'cc1ce7ff5f2b05150d0f0083f8287215c705060d0f0000000000554889e54155'
     'e95104e9ffc3'),
    (0x98, '69e8180000000000', '56ea180000000000'),     # code segment p_filesz
    (0xa0, '69e8180000000000', '56ea180000000000'),     # ... and p_memsz
    (0x110, '586f080000000000', '686f080000000000'),    # data segment p_memsz (+ timestamp)
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
