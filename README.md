# After Effects on Linux

Run your **genuine** Adobe After Effects (and Media Encoder) on Linux with Wine, set up to
feel at home on Linux Mint: native file dialogs, your own folders, your desktop theme and
fonts, NVIDIA GPU acceleration bridges, and the Wine bugs that stop After Effects from
starting or signing in fixed.

> This project does not contain or download any Adobe software. You need your own
> installer and an Adobe account (Creative Cloud plan or Adobe's free trial). The tools
> check Adobe's code signatures and refuse to set up installs whose files were modified.

## What it does

| Problem under plain Wine/Proton | Fix |
| --- | --- |
| AE 2020 crashes at "Initializing MediaCore" | `winmm` wrote an 8-byte size into a 4-byte buffer; patched to match Windows ([0001](patches/0001-winmm-instance-id-size-is-a-ULONG.patch)) |
| Crash in the text engine (`SLOCoolTypeFont.cpp`) | Microsoft core fonts (Adobe's font engine needs `ArialMT` & co.) |
| "Error parsing properties list" | Native MSXML 3/6 (+ the 64-bit `msxml3r.dll` winetricks misses) |
| Adobe sign-in window stuck on "Loading…" | Three `mshtml` fixes ([0002](patches/0002-mshtml-queryCommandSupported-returns-FALSE.patch), [0003](patches/0003-mshtml-honor-FEATURE_BROWSER_EMULATION.patch), [0004](patches/0004-mshtml-location-port-empty-for-default-ports.patch)) |
| Open/Save/Import show Wine's old dialog inside the prefix | `filedialog.dll` serves `IFileOpenDialog`/`IFileSaveDialog` with your desktop's own file chooser (xdg-desktop-portal), including AE's extra import options |
| Desktop, Documents, … are empty folders inside the prefix | Linked to your real folders |
| Windows-XP-looking menus, dialogs and title bars | Colours, fonts and font smoothing taken from your GTK theme; dark title bars with dark themes |
| Windows-style title bar buttons under Cinnamon/GNOME | Proton turns window-manager decorations off under Mutter-based WMs (Muffin says "Mutter (Muffin)"); patched so the desktop draws real title bars ([0005](patches/0005-winex11-decorate-windows-under-Mutter.patch)) |
| Jagged buttons, radio buttons, knobs and graph-editor curves | Adobe's UI draws through GDI+ with anti-aliasing on, which Wine's GDI+ ignores; Microsoft's GDI+ is installed instead (only the ~70 MB of Microsoft's Windows 7 SP1 package that hold it are downloaded, then checked by SHA-256) |
| Menus: greyed items with a white "engraved" shadow, blue hover | Menus drawn with the theme's menu colours, GTK-style hover and roomier rows ([0006](patches/0006-win32u-draw-menus-with-the-theme-colours.patch)) |
| Viewer one redraw behind on NVIDIA: paused frame stuck at draft resolution, laggy text selection, mask paths appearing late, ghosting when resizing panels | OpenGL child windows render offscreen and Wine copies them on screen; without `GLX_OML_sync_control` the copy ran before the vsynced swap finished. Offscreen swaps now skip vsync and finish first ([0007](patches/0007-winex11-show-the-current-frame-of-offscreen-GL.patch)) |
| Laggy typing, slow start of text editing | Keys go straight to Wine instead of through the ibus/fcitx XIM bridge (`ADOBE_WINE_IM=1` keeps it, for CJK input) |
| Splash screen text panel boxed in a shadow | Compositor shadow turned off for borderless popups, as on Windows |
| No CUDA / GPU sniffing confusion | DXVK, vkd3d-proton, DXVK-NVAPI and NVIDIA's CUDA/NVENC bridges from Proton-CachyOS |

Everything runs in its own Wine prefix with a private, patched copy of
[Proton-CachyOS](https://github.com/CachyOS/proton-cachyos) 11.0 — Steam/Heroic games are
not touched.

## Status

| App | Version | State |
| --- | --- | --- |
| After Effects 2020 | 17.7 | tested: starts, sign-in page, UI theme; native file dialogs verified with a test program |
| Media Encoder 2020 | 14.9 | in progress |
| After Effects 2018–2019, 2021–2026 | — | experimental: detected and set up, not yet tested |

## Install

```sh
sudo apt install python3-gi python3-xlib python3-cryptography curl xz-utils cabextract unzip zenity xdg-utils
git clone https://github.com/xsobhi/after-effects-linux.git
cd after-effects-linux
./install.sh
```

`install.sh` downloads the pinned Proton-CachyOS build (SHA-256 checked), patches it,
installs the tools to `~/.local/share/adobe-wine/app` and sets up every Wine prefix where it
finds a genuine After Effects / Media Encoder (or creates `~/.local/share/adobe-wine/prefix`).

### Installing After Effects

Open **After Effects Linux Setup** from the menu, or run:

```sh
ae-linux install-app /path/to/your/Adobe/Set-up.exe
```

Sign in when the installer asks — Adobe shows a QR code you can scan with your phone, or a
link to open in your browser.

### Already have AE in another Wine prefix?

Double-click **After Effects Linux Setup**: it searches `~/.wine`, Bottles, Lutris (`~/Games`),
Heroic, PlayOnLinux and Steam compatdata, lists what it found (version, tested or
experimental, files genuine or modified), and sets up the ones you tick.

### Plugins and other Windows installers

Double-click any `.exe`, `.msi`, `.lnk` or `.bat` in your file manager: it runs in the Adobe
prefix with the patched runner (`adobe-wine-open FILE` does the same from a terminal), so plugin
installers find After Effects through its registry entries and install where it looks. Each
run is logged to `~/.local/share/adobe-wine/logs/open-<name>.log`.

## Commands

```
ae-linux scan                    list installs found in Wine prefixes
ae-linux setup [PREFIX...]       (re)apply everything and create menu entries
ae-linux install-app SETUP.exe   run an Adobe installer in the prefix
ae-linux theme [PREFIX]          re-apply after changing your desktop theme
ae-linux verify [PREFIX]         check all Adobe files against Adobe's signatures
adobe-wine PROGRAM.exe           run anything in the Adobe prefix (winecfg, regedit, …)
```

## Tips

- On hybrid-GPU laptops, plug in: battery power-saving profiles throttle the CPU and GPU
  hard, which shows up as stutter in the timeline.
- Text is rendered by FreeType, so it looks slightly different from Windows ClearType.

## Troubleshooting

- Apps started from the menu log Wine errors and drag-and-drop events to
  `~/.local/share/adobe-wine/logs/<app>.log` (previous run: `.log.1`); `ADOBE_WINE_LOG=-` turns it off.
- Open/Save dialog calls are traced to `C:\users\steamuser\AppData\Local\Temp\adobe-filedialog.log`
  inside the prefix.
- `ae-linux verify` shows any Adobe file that no longer matches Adobe's signature.
- Something slow? Run `dev/ae-profile.sh 15` and repeat the slow action for 15 seconds: it
  prints CPU per thread and where the app's main thread spends its time (stack samples).

## Uninstall

```sh
./uninstall.sh          # tools, menu entries, file associations (keeps your prefixes)
./uninstall.sh --all    # also the runner and the default prefix
```

## How it works

- `lib/patch_runner.py` applies the fixes in `patches/` as small binary patches to the
  pinned runner build, refusing any file whose SHA-256 it does not know.
- `src/filedialog/` is a COM server registered (in the Adobe prefix only) for
  `CLSID_FileOpenDialog`/`CLSID_FileSaveDialog`; it hands each request to
  `lib/filechooser.py`, which talks to `org.freedesktop.portal.FileChooser`. Build it with
  [Zig](https://ziglang.org): `ZIG=zig src/filedialog/build.sh` (a prebuilt copy is in `prebuilt/`).
- `lib/theme.py` turns the GTK theme's colours and fonts into Wine registry settings;
  `lib/wm_helper.py` adds the window-manager hints Wine leaves out.

## License

MIT (see `LICENSE`). The files in `patches/` modify Wine and follow Wine's LGPL-2.1-or-later.
Not affiliated with Adobe. Adobe and After Effects are trademarks of Adobe Inc.

Built on Wine, Proton-CachyOS, DXVK, vkd3d-proton, dxvk-nvapi, nvidia-libs and winetricks.
