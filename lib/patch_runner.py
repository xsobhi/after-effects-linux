#!/usr/bin/env python3
"""Apply the Adobe compatibility fixes to a Proton-CachyOS 11.0 runner copy.

Usage: patch_runner.py RUNNER_FILES_DIR      (the runner's "files" directory)

Each patch lists its file offset with the original and the patched bytes, and the file's
SHA-256 before patching, so an unknown build is refused instead of being corrupted.
Running it again on an already patched runner changes nothing.

Fixes (source-level descriptions in patches/*.patch):
  winmm   DRV_QUERYFUNCTIONINSTANCEIDSIZE stores a ULONG like Windows, not 8 bytes
          (the extra 4 bytes zeroed a pointer in AE's dvaaudiodevice.dll -> crash).
  mshtml  queryCommandSupported returns FALSE instead of E_NOTIMPL; <!DOCTYPE> pages
          default to IE11 mode (what FEATURE_BROWSER_EMULATION=11001 asks for); and
          location.port is "" for default ports. Needed by Adobe's sign-in page.
          setAttribute("on<event>", "code") in IE9+ document mode also sets a working
          event handler, as in IE (Wine only stored the text): Adobe's installers attach
          the Install/Continue button actions that way (code caves: src/runner-caves).
  winex11 the window manager decorates windows under Mutter-based WMs again (Proton turns
          that off there; Muffin says "Mutter (Muffin)"). Offscreen OpenGL child windows
          (AE's viewer) swap without vsync and glFinish before Wine copies them on screen:
          without GLX_OML_sync_control (NVIDIA) the copy showed the previous frame.
  win32u  menus in the theme's colours: disabled items without the white "engraved"
          shadow, the hot item in the menu-highlight colour, roomier popup rows.
  cmd     DEL of a file that does not exist (or cannot be deleted) leaves ERRORLEVEL at
          0 as on Windows; Wine set 1, so installer scripts ending in a cleanup DEL
          "failed" (Maxon App: err.sys.script-execution-failed, preflight).
          cmd /c SCRIPT.bat exits with the last command's exit code, not ERRORLEVEL, as on
          Windows: Red Giant preflight scripts end with ECHO after taskkill of a service
          that is not running (128), and Wine returned that 128 (Magic Bullet, Universe).
  dwrite  Direct2D/DirectWrite text in the natural rendering modes (what D2D apps get
          by default) is drawn with FreeType's light hinting and without embedded bitmaps,
          like Windows' natural modes; Wine loaded glyphs with full TrueType hinting, so
          text looked like Windows 98. Aliased (1-bit) text keeps full hinting.
  server  ACEs matching the current user set a folder's Unix write bits whatever its owner
          SID (Adobe installers made "caps" read-only in older prefixes: error 105).
  crypt32 base64 of 48*n bytes ends with one line break, not two (Red Giant licence hang).
  explorer folder windows and /select,FILE open in the Linux file manager (winereveal.exe).
"""
import hashlib
import os
import shutil
import sys

from wine_caves import CRYPT32_64, EXPLORER_64
from mshtml_caves import ONEVENT32, ONEVENT64

CAVE64 = ('448b4ddc4181f9bb0100000f849effffff4183f9500f8494ffffff488d75e0e9b4ffffff')
CAVE32 = ('8b45dc3dbb0100000f8486ffffff83f8500f847dffffff8d75e0e9afffffff')

RUNNER = 'cachyos-11.0-20260703'
PATCHES = {
    'lib/wine/x86_64-windows/winmm.dll': (
        '87e45870d18637db340af40f5df025d24e249d596ceea052e367ac29b4ed3220', [
            (0x28877, '488907', '890790'),             # waveOutMessage
            (0x26e37, '488907', '890790'),             # waveInMessage
        ]),
    'lib/wine/x86_64-windows/mshtml.dll': (
        '9a97ea3e7b071bbbb1b768a6f9a4ba76bf7b50609a39185fca0226c727ee20d7', [
            (0x58870, '5556534883ec40488d6c24404889', '4d85c074066641c700000031c0c3'),
            (0x10bb61, 'ba02000000', 'ba06000000'),
            (0x83d89, '0f8581000000', '660f1f440000'),
            (0x83de0, '448b4ddc488d75e0', 'e92b000000909090'),
            (0x83e10, '488d41d848895424284c8d0d26930d00b90300000048894424204c8d05af301100488d15', CAVE64),
        ] + ONEVENT64),
    'lib/wine/x86_64-unix/winex11.so': (
        'fa03c9c29de8af9eaf64ad9ddbc03954e1c10925c70072fee3cabd32db4ee02f', [
            (0x44d4c, 'e81ff1ffff', '31c00f1f00'),     # GetWindowStyleMasks: HasWindowManager("Mutter") -> 0
            (0x44f2e, 'e83defffff', '31c00f1f00'),     # set_mwm_hints: same check
            # x11drv_surface_swap: XFlush -> call glfinish_flush below
            (0x35110, '498b7d00e8f77dfdff', 'e8ebdf02000f1f4000'),
            # glfinish_flush: sub rsp,8; funcs->p_glFinish(); XFlush(*r13 = gdi_display); ret
            (0x63100, '00' * 31, '4883ec08488b0595ed0100ff9070080000498b7d00e8f69dfaff4883c408c3'),
            # x11drv_surface_flush: interval = offscreen_interval()
            (0x35420, '458b6c2434', 'e8fbdc0200'),
            # offscreen_interval: r13d = base->interval, or 0 if base->client->offscreen.
            # The offscreen copy is presented by Wine, not by the driver; with vsync the
            # driver finishes the swap at the next vblank, after Wine already copied.
            (0x63120, '00' * 26, '458b6c2434498b4424204885c0740a8b402c85c0740345' + '31edc3'),
            (0x98, 'f1700500', '3a710500'),            # code segment p_filesz/p_memsz
            (0xa0, 'f1700500', '3a710500'),            # ... now include both helpers
        ]),
    # 32-bit programs (installers, most plugin installers) use their own unix libraries.
    'lib/wine/i386-unix/winex11.so': (
        'f92fb80fd86252f030b9592728ebc03d9c71bd0cb00d4c518bf059657a501a2b', [
            (0x3fbfb, 'e890f1ffff', '31c00f1f00'),     # GetWindowStyleMasks: HasWindowManager("Mutter") -> 0
            (0x3fe29, 'e862efffff', '31c00f1f00'),     # set_mwm_hints: same check
        ]),
    'lib/wine/x86_64-unix/win32u.so': (
        'cc68ef24f80d15ff4fc7df598910a1437b09f4a64dcca83594678dbebe75a1a8', [
            (0x100b40, '7440', 'eb40'),                # draw_menu_item: grayed text, no emboss
            (0x100bf4, '7424', 'eb24'),                # ... and its shortcut text
            (0x100c90, 'bf0e000000', 'bf07000000'),    # hot item text: COLOR_MENUTEXT
            (0x100ead, 'bf0d000000', 'bf1d000000'),    # hot item fill: COLOR_MENUHILIGHT
            (0xff6be, '8d5004', '8d5008'),             # calc_menu_item_size: row = text + 8
        ]),
    'lib/wine/x86_64-unix/dwrite.so': (
        '53c6bd6df0d517af6320819f9c138231ce876f35e38fa7ca13582996d75faa1e', [
            # get_glyph_bitmap: FT_Load_Glyph flags from glyph_load_flags (both call sites)
            (0x1be8, '31d28b730c', 'e853140000'),
            (0x1c3d, '8b730cba08000000', 'e8021400000f1f00'),
            # glyph_load_flags: edx = 0 or 8; unless mode == ALIASED: |= TARGET_LIGHT | NO_BITMAP
            (0x3040, '00' * 27, '31d2eb07ba08000000eb008b730c837b1001740681ca08000100c3'),
            # get_glyph_bbox: the same flags, so bitmaps fit their boxes (no mode passed here)
            (0x2e76, '31d28b730c', 'e8e5010000'),
            (0x2f47, '8b730cba08000000', 'e8140100000f1f00'),
            (0x3060, '00' * 9, '8b730cba08000100c3'),          # mov esi,glyph; edx = 0x10008
            (0x98, '3520000000000000', '6920000000000000'),   # code segment p_filesz
            (0xa0, '3520000000000000', '6920000000000000'),   # ... and p_memsz
        ]),
    'lib/wine/i386-unix/dwrite.so': (
        '2379143d6f8d8cd8d90eef75f890f5a13441518832e0079b9770ae273ac2cbd7', [
            # same; the helpers take over the 'sub esp,4; push flags; push glyph' sequence
            (0x1ad0, '83ec046a00ff760c', 'e83b1000000f1f00'),
            (0x1b27, '83ec046a08ff760c', 'e8041000000f1f00'),
            (0x2b10, '00' * 23, '5a83ec0431c0837e10017405b80800010050ff760cffe2'),
            (0x2b30, '00' * 26, '5a83ec04b808000000837e10017405b80800010050ff760cffe2'),
            (0x292b, '83ec046a00ff770c', 'e8200200000f1f00'),   # get_glyph_bbox
            (0x2a16, '83ec046a08ff770c', 'e8350100000f1f00'),
            (0x2b50, '00' * 14, '5a83ec046808000100ff770cffe2'),
            (0x64, '041b0000', '5e1b0000'),
            (0x68, '041b0000', '5e1b0000'),
        ]),
    'lib/wine/x86_64-windows/cmd.exe': (
        '51b46b725388d7b6036f2cab7f01d2bd2dc23327d26aea9a8839e9a3efd4bc1e', [
            (0xc299, '7507', 'eb07'),                  # WCMD_delete: never errorlevel = 1 per file
            (0x3034c, '0f85', '90e9'),                 # wmain, cmd /c: last command's exit code
        ]),
    'lib/wine/i386-windows/cmd.exe': (
        'c4a5180bc0e0d05f7f6cb4014ef7eecc36f61f2507963410040678dd477a37ce', [
            (0xc943, '750a', 'eb0a'),                  # same in the 32-bit build
            (0x32395, '0f85', '90e9'),                 # same in the 32-bit build
        ]),
    'lib/wine/i386-windows/mshtml.dll': (
        'd33decb1d3790abe00e49d54800998692f25295a2d29bef46650d7659479b125', [
            (0x58c40, 'f605a002151001750fb801400080c20c008d', '8b44240c85c0740566c700000031c0c20c00'),
            (0x110835, 'ba02000000', 'ba06000000'),
            (0x85385, '0f859d000000', '660f1f440000'),
            (0x853f0, '8b45dc8d75e0', 'e93300000090'),
            (0x85428, '8d46ec895c241489442410c744240c6ef01510c744240820da1810c7442404', CAVE32),
            # The DLL is usually rebased (32-bit): base relocations for absolute addresses in
            # the replaced code would rewrite 4 bytes of the new code. Make them no-ops.
            (0x22c91c, '423c', '0000'),                # reloc at 0x58c42
            (0x22f96a, '3734', '0000'),                # reloc at 0x85437
            (0x22f96c, '3f34', '0000'),                # reloc at 0x8543f
        ] + ONEVENT32),
    'bin/wineserver': (
        '22fc7c7f322b99a788f1fd761bb68a37437b3653963a6143e983e34925ba294f', [
            (0x33d13, '0f85f7010000', 'e9f801000090'),  # sd_to_mode, deny ACE: skip owner check
            (0x33db4, '0f8516010000', 'e91701000090'),  # allow ACE: the same
        ]),
    'lib/wine/x86_64-windows/crypt32.dll': CRYPT32_64,
    'lib/wine/x86_64-windows/explorer.exe': EXPLORER_64,
}
HERE = os.path.dirname(os.path.abspath(__file__))


def patch_file(path, original_sha, patches):
    with open(path, 'rb') as f:
        data = bytearray(f.read())
    if all(data[o:o + len(bytes.fromhex(new))] == bytes.fromhex(new) for o, _, new in patches):
        return 'already patched'
    for offset, old, new in patches:        # undo an older patch set so new entries can be added
        if data[offset:offset + len(bytes.fromhex(new))] == bytes.fromhex(new):
            data[offset:offset + len(bytes.fromhex(new))] = bytes.fromhex(old)
    if hashlib.sha256(data).hexdigest() != original_sha:
        raise SystemExit(f'{path}: unexpected build (need Proton {RUNNER}); not patching')
    for offset, old, new in patches:
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        assert len(old) == len(new) and data[offset:offset + len(old)] == old, hex(offset)
        data[offset:offset + len(new)] = new
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.chmod(tmp, 0o755)                    # the new file replaces the old one: keep it executable
    os.replace(tmp, path)
    return f'patched ({len(patches)} changes)'


def install_gecko_prefs(files):
    src = os.path.join(HERE, '..', 'share', 'gecko-prefs.js')
    gecko = os.path.join(files, 'share', 'wine', 'gecko')
    for entry in sorted(os.listdir(gecko)) if os.path.isdir(gecko) else []:
        prefs = os.path.join(gecko, entry, 'defaults', 'pref')
        if os.path.isdir(prefs):
            os.chmod(prefs, 0o755)
            shutil.copyfile(src, os.path.join(prefs, 'adobe-wine.js'))
            print(f'  gecko prefs -> {entry}')


def main(files):
    for rel, (sha, patches) in PATCHES.items():
        print(f'  {rel}: {patch_file(os.path.join(files, rel), sha, patches)}')
    install_gecko_prefs(files)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
