# shellcheck shell=bash
# Prepare (or refresh) a Wine prefix for Adobe apps. Idempotent; sourced by install.sh and
# ae-linux. Needs lib/common.sh and LIB_DIR pointing at lib/.
# shellcheck source=gpu_libs.sh
source "$LIB_DIR/gpu_libs.sh"
# shellcheck source=vcruntime.sh
source "$LIB_DIR/vcruntime.sh"
# shellcheck source=gdiplus.sh
source "$LIB_DIR/gdiplus.sh"

run_winetricks() {  # run_winetricks PREFIX VERB...
    local wt="$CACHE_DIR/winetricks-$WINETRICKS_VERSION"
    download "$WINETRICKS_URL" "$WINETRICKS_SHA256" "$wt"
    chmod +x "$wt"
    WINEPREFIX="$1" WINE="$BIN_DIR/adobe-wine" WINESERVER="$RUNNER_DIR/files/bin/wineserver" \
        ADOBE_WINE_PREFIX="$1" "$wt" -q --unattended "${@:2}" > "$CACHE_DIR/winetricks.log" 2>&1 ||
        die "winetricks ${*:2} failed; see $CACHE_DIR/winetricks.log"
}

install_filedialog() {  # install_filedialog PREFIX REG
    local pfx=$1 reg=$2 clsid
    install -m 755 "$APP_DIR/filedialog.dll" "$pfx/drive_c/windows/system32/adobe-filedialog.dll"
    for clsid in "${FILEDIALOG_CLSIDS[@]}"; do
        printf '\r\n[HKEY_LOCAL_MACHINE\\Software\\Classes\\CLSID\\%s\\InprocServer32]\r\n' "$clsid"
        printf '@="C:\\\\windows\\\\system32\\\\adobe-filedialog.dll"\r\n"ThreadingModel"="Apartment"\r\n'
    done >> "$reg"
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
    import_reg "$pfx" "$reg"
    msxml_progids "$pfx"
    # TEMP must stay an expandable string (Proton's user is "steamuser"; adopted prefixes may
    # point at another profile). Wine's regedit misreads hex(2) in UTF-8 .reg files, so use reg.
    for v in TEMP TMP; do
        wine_in "$pfx" reg add 'HKCU\Environment' /v "$v" /t REG_EXPAND_SZ \
            /d '%USERPROFILE%\AppData\Local\Temp' /f >/dev/null 2>&1
    done
    stop_prefix "$pfx"
    rm -f "$reg"
    say "Matching the desktop theme, fonts and folders"
    apply_theme "$pfx"
    "$LIB_DIR/user_folders.sh" "$pfx"
    gecko_prefs "$pfx"
}
