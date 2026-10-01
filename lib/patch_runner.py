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
  winex11 let the window manager decorate windows under Mutter-based WMs again: Proton
          turns decorations off there, and Cinnamon's Muffin reports itself as "Mutter
          (Muffin)", so every window got Wine-drawn, Windows-style title bars.
          Also: OpenGL child windows (AE's viewer) render offscreen and are copied on
          screen after each swap; without GLX_OML_sync_control (NVIDIA) the copy ran
          before the asynchronous, vsynced swap finished and showed the previous frame.
          Offscreen drawables now swap without vsync and glFinish before the copy
          (helpers placed in the code segment's tail padding).
  win32u  menus drawn like the desktop's: disabled items in the theme's disabled colour
          (not fixed grey with a white "engraved" shadow), the hot item filled with the
          menu-highlight colour and keeping the menu text colour, roomier popup rows.
"""
import hashlib
import os
import shutil
import sys

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
        ]),
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
    'lib/wine/x86_64-unix/win32u.so': (
        'cc68ef24f80d15ff4fc7df598910a1437b09f4a64dcca83594678dbebe75a1a8', [
            (0x100b40, '7440', 'eb40'),                # draw_menu_item: grayed text, no emboss
            (0x100bf4, '7424', 'eb24'),                # ... and its shortcut text
            (0x100c90, 'bf0e000000', 'bf07000000'),    # hot item text: COLOR_MENUTEXT
            (0x100ead, 'bf0d000000', 'bf1d000000'),    # hot item fill: COLOR_MENUHILIGHT
            (0xff6be, '8d5004', '8d5008'),             # calc_menu_item_size: row = text + 8
        ]),
    'lib/wine/i386-windows/mshtml.dll': (
        'd33decb1d3790abe00e49d54800998692f25295a2d29bef46650d7659479b125', [
            (0x58c40, 'f605a002151001750fb801400080c20c008d', '8b44240c85c0740566c700000031c0c20c00'),
            (0x110835, 'ba02000000', 'ba06000000'),
            (0x85385, '0f859d000000', '660f1f440000'),
            (0x853f0, '8b45dc8d75e0', 'e93300000090'),
            (0x85428, '8d46ec895c241489442410c744240c6ef01510c744240820da1810c7442404', CAVE32),
        ]),
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
    os.chmod(path, 0o755)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
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
