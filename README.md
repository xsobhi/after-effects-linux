# After Effects on Linux

Run your Adobe After Effects (and Media Encoder) on Linux with Wine, set up to
feel at home on Linux Mint: native file dialogs, your own folders, your desktop theme and
fonts, NVIDIA GPU acceleration bridges, and the Wine bugs that stop After Effects from
starting or signing in fixed.

> This project does not contain or download any Adobe software. You need your own
> installer and an Adobe account (Creative Cloud plan or Adobe's free trial). The tools
> discover Adobe installs in Wine prefixes and set them up without modifying the Adobe files.

## What it does

| Problem under plain Wine/Proton                                                                                                                            | Fix                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AE 2020 crashes at "Initializing MediaCore"                                                                                                                | `winmm` wrote an 8-byte size into a 4-byte buffer; patched to match Windows ([0001](patches/0001-winmm-instance-id-size-is-a-ULONG.patch))                                                                                                                                                                                |
| Crash in the text engine (`SLOCoolTypeFont.cpp`)                                                                                                           | Microsoft core fonts (Adobe's font engine needs `ArialMT` & co.)                                                                                                                                                                                                                                                          |
| "Error parsing properties list"                                                                                                                            | Native MSXML 3/6 (+ the 64-bit `msxml3r.dll` winetricks misses)                                                                                                                                                                                                                                                           |
| Adobe sign-in window stuck on "Loading…"; 32-bit Adobe installers crash when it opens                                                                      | Three `mshtml` fixes ([0002](patches/0002-mshtml-queryCommandSupported-returns-FALSE.patch), [0003](patches/0003-mshtml-honor-FEATURE_BROWSER_EMULATION.patch), [0004](patches/0004-mshtml-location-port-empty-for-default-ports.patch))                                                                                  |
| Open/Save/Import show Wine's old dialog inside the prefix                                                                                                  | `filedialog.dll` serves `IFileOpenDialog`/`IFileSaveDialog` with your desktop's own file chooser (xdg-desktop-portal), including AE's extra import options                                                                                                                                                                |
| Desktop, Documents, … are empty folders inside the prefix                                                                                                  | Linked to your real folders                                                                                                                                                                                                                                                                                               |
| Windows-XP-looking menus, dialogs and title bars                                                                                                           | Colours, fonts and font smoothing taken from your GTK theme; dark title bars with dark themes                                                                                                                                                                                                                             |
| Windows-style title bar buttons under Cinnamon/GNOME                                                                                                       | Proton turns window-manager decorations off under Mutter-based WMs (Muffin says "Mutter (Muffin)"); patched so the desktop draws real title bars, for 64-bit apps and 32-bit installers alike ([0005](patches/0005-winex11-decorate-windows-under-Mutter.patch))                                                          |
| Jagged buttons, radio buttons, knobs and graph-editor curves                                                                                               | Adobe's UI draws through GDI+ with anti-aliasing on, which Wine's GDI+ ignores; Microsoft's GDI+ is installed instead (only the ~70 MB of Microsoft's Windows 7 SP1 package that hold it are downloaded, then checked by SHA-256)                                                                                         |
| Menus: greyed items with a white "engraved" shadow, blue hover                                                                                             | Menus drawn with the theme's menu colours, GTK-style hover and roomier rows ([0006](patches/0006-win32u-draw-menus-with-the-theme-colours.patch))                                                                                                                                                                         |
| Viewer one redraw behind on NVIDIA: paused frame stuck at draft resolution, laggy text selection, mask paths appearing late, ghosting when resizing panels | OpenGL child windows render offscreen and Wine copies them on screen; without `GLX_OML_sync_control` the copy ran before the vsynced swap finished. Offscreen swaps now skip vsync and finish first ([0007](patches/0007-winex11-show-the-current-frame-of-offscreen-GL.patch))                                           |
| Hybrid NVIDIA laptops: preview plays at ~22 fps instead of 30, playhead stalls then jumps | With PRIME render offload the NVIDIA driver hands each finished frame to the X server from its own connection; Wine copied the viewer right after the swap and often got the previous frame (4-20 of 90 frames never reached the screen). A 2 ms pause after the swap lets the frame land first: 0 of 90 lost, AE's viewer at 27 fps like on the Intel GPU ([0015](patches/0015-winex11-wait-for-the-PRIME-offload-frame-before-copying.patch)) |
| Laggy typing, slow start of text editing                                                                                                                   | Keys go straight to Wine instead of through the ibus/fcitx XIM bridge (`ADOBE_WINE_IM=1` keeps it, for CJK input)                                                                                                                                                                                                         |
| Buttons, check boxes, radio buttons, combo boxes, scroll bars look like Windows 2000                                                                       | A Windows visual style is generated from your GTK theme at setup (`lib/msstyles/`): GTK draws the controls' states, the rest of Wine's Light theme is recoloured to your palette. `ae-linux theme` rebuilds it after you change the desktop theme                                                                         |
| Installers whose batch scripts end with a clean-up `del` fail (Maxon App: "Script execution failed for task: preflight")                                   | `del` of a missing file leaves `%ERRORLEVEL%` at 0 as on Windows ([0008](patches/0008-cmd-del-keeps-errorlevel-0-for-missing-files.patch))                                                                                                                                                                                |
| Adobe installer: clicking Install/Continue does nothing                                                                                                    | The installer page attaches the button's action with `setAttribute("onclick", "…")`; Wine stored the text but never turned it into a handler. Such `on…` attributes now get a working event handler (and removing them clears it), as in IE 9-11 ([0009](patches/0009-mshtml-setAttribute-compiles-event-handlers.patch)) |
| Red Giant installers (Magic Bullet Suite, Universe) fail near the end: "Status 11015 … Script execution failed for task: preflight"                        | Their preflight scripts end with `echo` after `taskkill` of a service that isn't running (exit 128). `cmd /c script.bat` now exits with the last command's code, as on Windows, instead of the leftover `ERRORLEVEL` ([0010](patches/0010-cmd-c-returns-the-last-command-exit-code.patch))                                |
| Adobe installers stop with "Sorry, installation failed … (Error Code: 105)" (Media Encoder, Photoshop)                                                     | Adobe's installers and apps re-apply the permissions of `Common Files\Adobe\caps`; in a prefix first used with another Wine build (different user SID), Wine dropped the folder's write bit, so `hdpim.db` could not be updated. Permission entries that match the current user now count whatever owner the folder has ([0011](patches/0011-server-folder-write-bits-follow-the-current-user.patch)) |
| Media Encoder hangs at start-up on "Loading 3DStroke.aex" (Red Giant plugins)                                                                              | The plugins send their licence request to the Red Giant service as base64 made by `CryptBinaryToStringA`; for a multiple of 48 bytes Wine ended the text with two line breaks and no NUL, the request picked up stray bytes, the service could not decrypt it and never answered. Base64 text now ends with one line break, as on Windows ([0012](patches/0012-crypt32-base64-ends-with-one-line-break.patch)) |
| Clicking an output file in Media Encoder (or any "show in folder") opens Wine's file browser                                                               | Wine's `explorer.exe` hands folders and `/select,FILE` to `winereveal.exe`, which opens your Linux file manager with the file selected (`org.freedesktop.FileManager1`, else `xdg-open`) ([0013](patches/0013-explorer-folders-open-in-the-linux-file-manager.patch))                                                     |
| Heavy ghosting while scrolling the Effects & Presets panel (pieces of the timeline flash inside it)                                                        | AE scrolls its stacked panels by moving tall child windows; Wine copied their whole old rectangle, including what lay outside the panel, and never repainted it. Only the visible part is copied now and the rest is repainted before the next frame ([0014](patches/0014-win32u-moved-child-windows-copy-only-visible-bits.patch)) |
| Video Copilot installers / FX Console show no text (Direct2D apps)                                                                                         | DirectWrite only sees fonts in the registry font list and falls back on Tahoma. Proton's fonts are linked into `C:\windows\Fonts` and registered, stale "External Fonts" records that made Wine delete those entries are removed, and `adobe-wine` puts them back (`ae-linux fonts`) if they ever go missing              |
| Fonts installed on Linux: Helvetica missing from AE's font menu, Tahoma or Courier New Bold listed wrongly, real Microsoft fonts shown as look-alikes | Wine passes the desktop's fonts (`~/.local/share/fonts`, `/usr/share/fonts`) to Windows programs, but its "Helvetica → Arial" and "Times → Times New Roman" substitutes hid an installed Helvetica, Proton's look-alikes (Noto Sans named "Microsoft Sans Serif", …) were found before the real Microsoft fonts, and Adobe's font list cache kept entries of replaced fonts. Substitutes are dropped when the real font is installed, `C:\windows\Fonts` points at the real Microsoft fonts when you have them, and the Adobe font list is rebuilt after fonts are installed or removed (`adobe-wine` checks at each start; `ae-linux fonts`) |
| VC++ 2015-2022 redistributable setups fail: "Failed to load manifest as XML document" (0x80040111)                                                         | Wine's builtin `msxml2` re-claims `Msxml2.DOMDocument` & co. on every prefix update, but with Microsoft's MSXML 3 installed those MSXML 2.6 classes don't exist; the names are pointed back at MSXML 3, as on Windows                                                                                                     |
| Splash screen text panel boxed in a shadow                                                                                                                 | Compositor shadow turned off for borderless popups, as on Windows                                                                                                                                                                                                                                                         |
| No CUDA / GPU sniffing confusion                                                                                                                           | DXVK, vkd3d-proton, DXVK-NVAPI and NVIDIA's CUDA/NVENC bridges from Proton-CachyOS                                                                                                                                                                                                                                        |

Everything runs in its own Wine prefix with a private, patched copy of
[Proton-CachyOS](https://github.com/CachyOS/proton-cachyos) 11.0 — Steam/Heroic games are
not touched.

## Status

| App                                | Version | State                                                                                    |
| ---------------------------------- | ------- | ---------------------------------------------------------------------------------------- |
| After Effects 2020                 | 17.7    | tested: starts, sign-in page, UI theme; native file dialogs verified with a test program |
| Media Encoder 2020                 | 14.9    | in progress                                                                              |
| After Effects 2018–2019, 2021–2026 | —       | experimental: detected and set up, not yet tested                                        |

## Install

```sh
git clone https://github.com/xsobhi/after-effects-linux.git
```

Then open the folder in your file manager and double-click **`install.sh`** (choose *Run*),
or run `./install.sh --gui`. The installer window walks you through it:

1. **Welcome** — checks the system packages it needs and installs missing ones for you
   (asks for your password), and lists the Adobe apps it already finds in Wine prefixes.
2. **Wine** — lists every Wine on the computer (system Wine, Steam and Heroic Proton,
   Lutris, Bottles, PlayOnLinux), marking the machine's default one. The recommended
   choice is preselected: Proton-CachyOS 11.0 with this project's fixes, downloaded if
   needed (SHA-256 checked). Any other Wine works without those fixes.
3. **Locations** — where the Windows environment (Wine prefix with your Adobe apps,
   plugins and presets; ~15 GB) and the Wine download go, with the free space shown.
4. **Adobe installer and options** — optionally your Adobe `Set-up.exe` to run right
   after setup; menu entries, opening `.exe`/`.msi` files with this Wine, desktop theme,
   NVIDIA GPU.
5. **Install** — progress and a detailed log.

Afterwards, **double-click any Windows installer** — another Adobe app, plugins (Red
Giant, Boris FX, Video Copilot, Maxon…) or presets — and it installs into this Wine, where
After Effects finds it. Run **After Effects Linux Setup** from the menu to change the
settings later.

From a terminal, the same choices are options (saved in `~/.config/adobe-wine/config`):

```sh
sudo apt install python3-gi python3-xlib python3-cryptography curl xz-utils cabextract unzip zenity xdg-utils
./install.sh [--prefix DIR] [--runner-dir DIR] [--wine DIR] [--adobe-installer Set-up.exe] \
             [--no-nvidia] [--no-theme] [--no-menu] [--no-exe-handler]
```

`install.sh` downloads the pinned Proton-CachyOS build, patches it, installs the tools to
`~/.local/share/adobe-wine/app` and sets up every Wine prefix where it finds an After
Effects / Media Encoder (or creates the chosen prefix).

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
experimental, files), and sets up the ones you tick.

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
ae-linux fonts [PREFIX]          refresh fonts now (otherwise done at the next app start)
ae-linux verify [PREFIX]         check all Adobe files against Adobe's signatures
adobe-wine PROGRAM.exe           run anything in the Adobe prefix (winecfg, regedit, …)
```

## Tips

- Install fonts the Linux way (double-click → Install, or copy them to `~/.local/share/fonts`):
  After Effects lists them from its next start. Variable fonts show their default style only.
- The red playhead moves every 50 ms during preview by default; for a smoother line set
  "Time needle scrub and preview update frequency (seconds)" to `0.016000` in
  `Adobe After Effects 17.7 Prefs.txt` (AE closed).
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
  pinned runner build, refusing any file whose SHA-256 it does not know. Fixes that need new
  code are assembled from `src/runner-caves/` (`build.py` writes `lib/mshtml_caves.py`).
- `src/filedialog/` is a COM server registered (in the Adobe prefix only) for
  `CLSID_FileOpenDialog`/`CLSID_FileSaveDialog`; it hands each request to
  `lib/filechooser.py`, which talks to `org.freedesktop.portal.FileChooser`. Build it with
  [Zig](https://ziglang.org): `ZIG=zig src/filedialog/build.sh` (a prebuilt copy is in `prebuilt/`).
- `lib/msstyles/build.py` reads Wine's Light visual style from the prefix, recolours it and
  replaces the common controls with images GTK renders in each state, then writes
  `C:\windows\resources\themes\desktop\desktop.msstyles` (nothing from Wine is shipped here).
- `lib/theme.py` turns the GTK theme's colours and fonts into Wine registry settings;
  `lib/wm_helper.py` adds the window-manager hints Wine leaves out.

## License

MIT (see `LICENSE`). The files in `patches/` modify Wine and follow Wine's LGPL-2.1-or-later.
Not affiliated with Adobe. Adobe and After Effects are trademarks of Adobe Inc.

Built on Wine, Proton-CachyOS, DXVK, vkd3d-proton, dxvk-nvapi, nvidia-libs and winetricks.
