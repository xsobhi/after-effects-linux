# shellcheck shell=bash
# Prepare (or refresh) a Wine prefix for Adobe apps. Idempotent; sourced by install.sh and
# ae-linux. Needs lib/common.sh and LIB_DIR pointing at lib/.
# shellcheck source=gpu_libs.sh
source "$LIB_DIR/gpu_libs.sh"
# shellcheck source=vcruntime.sh
source "$LIB_DIR/vcruntime.sh"
# shellcheck source=gdiplus.sh
source "$LIB_DIR/gdiplus.sh"
# shellcheck source=fonts.sh
source "$LIB_DIR/fonts.sh"

run_winetricks() {  # run_winetricks PREFIX VERB...
    local wt="$CACHE_DIR/winetricks-$WINETRICKS_VERSION"
    download "$WINETRICKS_URL" "$WINETRICKS_SHA256" "$wt"
    chmod +x "$wt"
    WINEPREFIX="$1" WINE="$BIN_DIR/adobe-wine" WINESERVER="$WINESERVER_BIN" \
        ADOBE_WINE_PREFIX="$1" "$wt" -q --unattended "${@:2}" > "$CACHE_DIR/winetricks.log" 2>&1 ||
        die "winetricks ${*:2} failed; see $CACHE_DIR/winetricks.log"
}

install_filedialog() {  # install_filedialog PREFIX REG
    local pfx=$1 reg=$2 clsid
    install -m 755 "$APP_DIR/filedialog.dll" "$pfx/drive_c/windows/system32/adobe-filedialog.dll"
    # explorer.exe hands folder windows / "explorer /select,FILE" to it (patches/0013)
    install -m 755 "$APP_DIR/winereveal.exe" "$pfx/drive_c/windows/system32/winereveal.exe"
    for clsid in "${FILEDIALOG_CLSIDS[@]}"; do
        printf '\r\n[HKEY_LOCAL_MACHINE\\Software\\Classes\\CLSID\\%s\\InprocServer32]\r\n' "$clsid"
        printf '@="C:\\\\windows\\\\system32\\\\adobe-filedialog.dll"\r\n"ThreadingModel"="Apartment"\r\n'
    done >> "$reg"
}

installed_copy() {  # installed_copy FONT — the same face installed on the desktop, if any
    local fam weight slant
    IFS='|' read -r fam weight slant < <(fc-scan --format '%{family[0]}|%{weight}|%{slant}\n' "$1" 2>/dev/null)
    [[ -n "$fam" ]] || return 0
    fam=$(sed 's/[\\:,=-]/\\&/g' <<< "$fam")
    fc-list --format '%{file}\n' "$fam:weight=$weight:slant=$slant" 2>/dev/null |
        { grep -v "^$(dirname "$(readlink -f "$1")")/" || true; } | LC_ALL=C sort | head -1
}

link_runner_fonts() {  # link_runner_fonts PREFIX REG — what Proton's launcher script does
    # Proton's Wine registers its bundled fonts (Tahoma, Marlett, Microsoft Sans Serif, MS
    # Gothic, SimSun, ...) by file name, expecting them in C:\windows\Fonts, where the
    # proton script normally symlinks them. Without them DirectWrite has no fallback font
    # (D2D apps draw no text at all) and GDI+ cannot find Tahoma. Real files are kept, so
    # Microsoft's core fonts (corefonts) win over Proton's metric-compatible copies, and
    # where the real Microsoft font is installed on the desktop (~/.local/share/fonts) the
    # link points at it instead of Proton's look-alike (Noto Sans named "Microsoft Sans
    # Serif", Source Han Sans named "Microsoft YaHei", ...), which would otherwise be found
    # first and hide it from GDI and Adobe's font menus.
    # DirectWrite only knows fonts listed in the registry (Proton's template prefix lists
    # them; wineboot does not), so register each linked file as Windows names it. Wine also
    # lists its own fonts under "External Fonts" with the runner's path; once the file is
    # in C:\windows\Fonts that record looks stale, and Wine's clean-up then deletes the
    # same-named Windows entry too (Tahoma vanished, D2D text again). Drop those records.
    local dir font target name style fonts=$1/drive_c/windows/Fonts entries=()
    mkdir -p "$fonts"
    printf '\r\n[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts]\r\n' >> "$2"
    for dir in "$RUNNER_FILES/share/fonts" "$RUNNER_FILES/share/wine/fonts"; do
        for font in "$dir"/*.ttf "$dir"/*.ttc; do
            [[ -e "$font" ]] || continue
            [[ -e "$fonts/${font##*/}" && ! -L "$fonts/${font##*/}" ]] && continue
            target=$(installed_copy "$font")
            target=${target:-$font}
            ln -sfn "$target" "$fonts/${font##*/}"
            name=$(fc-scan --format '%{family[0]}\n' "$target" 2>/dev/null | paste -sd'&' | sed 's/&/ \& /g')
            [[ -n "$name" ]] || continue
            # Style from weight/slant (fontconfig: bold >= 200, italic > 0), not localised names.
            style=$(fc-scan --format '%{weight} %{slant}\n' "$target" 2>/dev/null | head -1 |
                awk '{s = ($1 >= 200 ? " Bold" : ""); if ($2 > 0) s = s " Italic"; print s}')
            printf '"%s%s (TrueType)"="%s"\r\n' "$name" "$style" "${font##*/}" >> "$2"
            entries+=("$name$style (TrueType)")
            # Wine's own records are per face (full name), for each face of a collection
            mapfile -t -O "${#entries[@]}" entries < <(fc-scan --format '%{fullname[0]} (TrueType)\n' "$target" 2>/dev/null)
        done
    done
    printf '\r\n[HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\External Fonts]\r\n' >> "$2"
    printf '%s\n' "${entries[@]}" | LC_ALL=C sort -u | while IFS= read -r name; do
        printf '"%s"=-\r\n' "$name"
    done >> "$2"
}

fonts_reg() {  # fonts_reg PREFIX REG — font settings into REG; import it, then run fonts_done
    link_runner_fonts "$1" "$2"
    # Desktop fonts that a substitute hides (an installed Helvetica, listed as Arial)
    printf '\r\n[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes]\r\n' >> "$2"
    shadowed_substitutes "$1" | sed 's/[\\"]/\\&/g; s/.*/"&"=-\r/' >> "$2"
}

fonts_done() {  # fonts_done PREFIX — Adobe apps list the OS fonts afresh at their next start
    # CoolType's lists of OS fonts; rebuilt at start-up, see lib/fonts.sh
    find "$1/drive_c/users" -path '*/Adobe/*' \( -name 'AdobeFnt*OSFonts*.lst' -o -name 'AdobeFnt[0-9]*.lst' \) \
        -delete 2>/dev/null || true
    fonts_signature > "$1/.adobe-wine-fonts"
}

fix_fonts() {  # fix_fonts PREFIX — bring the fonts up to date (adobe-wine calls this when needed)
    local reg
    reg=$(mktemp --suffix=.reg)
    printf 'Windows Registry Editor Version 5.00\r\n' > "$reg"
    fonts_reg "$1" "$reg"
    import_reg "$1" "$reg"
    rm -f "$reg"
    fonts_done "$1"
}

msxml_progids() {  # msxml_progids PREFIX — version-independent MSXML names -> MSXML 3, as on Windows
    # Wine's builtin msxml2.dll claims Msxml2.DOMDocument & co. (MSXML 2.6 classes) on every
    # wineboot; with Microsoft's msxml3.dll those classes do not exist, so programs asking
    # for "Msxml2.DOMDocument" got CLASS_E_CLASSNOTAVAILABLE (VC++ redist setup: "Failed to
    # load manifest as XML document").
    local name clsid view
    for name in DOMDocument:F6D90F11 FreeThreadedDOMDocument:F6D90F12 XMLHTTP:F6D90F16; do
        clsid="{${name#*:}-9C73-11D3-B32E-00C04F990BB4}"
        for view in 64 32; do
            wine_in "$1" reg add "HKLM\\Software\\Classes\\Msxml2.${name%%:*}\\CLSID" /ve /d "$clsid" \
                /f /reg:$view >/dev/null 2>&1
            wine_in "$1" reg add "HKLM\\Software\\Classes\\Msxml2.${name%%:*}\\CurVer" /ve \
                /d "Msxml2.${name%%:*}.3.0" /f /reg:$view >/dev/null 2>&1
        done
    done
}

gecko_prefs() {  # copy the web-content colour prefs into Gecko copies installed in the prefix
    local d
    for d in "$1"/drive_c/windows/{system32,syswow64}/gecko/*/wine_gecko/defaults/pref; do
        [[ -d "$d" ]] && cp "$LIB_DIR/../share/gecko-prefs.js" "$d/adobe-wine.js"
    done
    return 0
}

import_reg() {  # import_reg PREFIX REG — into both the 64-bit and 32-bit registry views
    local pfx=$1 name
    name="adobe-wine-$$.reg"
    cp "$2" "$pfx/drive_c/windows/temp/$name"
    wine_in "$pfx" 'C:\windows\regedit.exe' /S "C:\\windows\\temp\\$name" >/dev/null 2>&1
    wine_in "$pfx" 'C:\windows\syswow64\regedit.exe' /S "C:\\windows\\temp\\$name" >/dev/null 2>&1
    rm -f "$pfx/drive_c/windows/temp/$name"
}

build_msstyles() {  # build_msstyles PREFIX — a Windows visual style drawn from the GTK theme
    local themes=$1/drive_c/windows/resources/themes
    [[ -f "$themes/light/light.msstyles" ]] || return 1
    python3 "$LIB_DIR/msstyles/build.py" "$themes/light/light.msstyles" \
        "$themes/desktop/desktop.msstyles" 2>/dev/null
}

apply_theme() {  # apply_theme PREFIX [--running] — re-run after changing the desktop theme
    local reg style=()
    reg=$(mktemp --suffix=.reg)
    if build_msstyles "$1"; then
        style=(--msstyles 'C:\windows\resources\themes\desktop\desktop.msstyles')
    else
        say "GTK rendering unavailable (python3-gi, -gi-cairo, -pil, a display): classic controls"
    fi
    python3 "$LIB_DIR/theme.py" "$reg" "${style[@]}"
    # --running: leave open apps alone; windows opened from now on get the new look.
    [[ "${2:-}" == --running ]] || stop_prefix "$1"
    import_reg "$1" "$reg"
    [[ "${2:-}" == --running ]] || stop_prefix "$1"
    rm -f "$reg"
}

setup_prefix() {  # setup_prefix PREFIX
    local pfx=$1 win=$1/drive_c/windows reg
    say "Preparing Wine prefix: $pfx"
    mkdir -p "$pfx"
    stop_prefix "$pfx"
    wine_in "$pfx" wineboot -u >/dev/null 2>&1 || die "wineboot failed for $pfx"
    stop_prefix "$pfx"
    # winetricks looks for C:\windows\Fonts with exactly that case.
    if [[ -d "$win/fonts" && ! -e "$win/Fonts" ]]; then mv "$win/fonts" "$win/Fonts"; fi
    say "Installing Microsoft core fonts and MSXML 3/6 (winetricks)"
    run_winetricks "$pfx" corefonts msxml3 msxml6
    stop_prefix "$pfx"
    # winetricks installs 64-bit msxml3.dll without its resource DLL; it will not load without one.
    if [[ ! -f "$win/system32/msxml3r.dll" && -f "$win/syswow64/msxml3r.dll" ]]; then
        cp "$win/syswow64/msxml3r.dll" "$win/system32/msxml3r.dll"
    fi
    reg=$(mktemp --suffix=.reg)
    printf 'Windows Registry Editor Version 5.00\r\n' > "$reg"
    install_vcruntime "$pfx" "$reg"
    install_gdiplus "$pfx" "$reg"
    install_gpu_libs "$pfx" "$reg"
    install_filedialog "$pfx" "$reg"
    fonts_reg "$pfx" "$reg"
    import_reg "$pfx" "$reg"
    fonts_done "$pfx"
    msxml_progids "$pfx"
    # TEMP must stay an expandable string (Proton's user is "steamuser"; adopted prefixes may
    # point at another profile). Wine's regedit misreads hex(2) in UTF-8 .reg files, so use reg.
    for v in TEMP TMP; do
        wine_in "$pfx" reg add 'HKCU\Environment' /v "$v" /t REG_EXPAND_SZ \
            /d '%USERPROFILE%\AppData\Local\Temp' /f >/dev/null 2>&1
    done
    stop_prefix "$pfx"
    rm -f "$reg"
    if [[ "${ADOBE_WINE_THEME:-1}" != 0 ]]; then
        say "Matching the desktop theme, fonts and folders"
        apply_theme "$pfx"
    fi
    "$LIB_DIR/user_folders.sh" "$pfx"
    gecko_prefs "$pfx"
}
