# shellcheck shell=bash
# Microsoft GDI+ (64-bit) for a prefix. Adobe's UI library (dvaui/drawbot) draws buttons,
# radio buttons, knobs and graph-editor curves through GDI+ with anti-aliasing on; Wine's
# own GDI+ ignores that and draws jagged edges. Same file as `winetricks gdiplus`, taken
# from Microsoft's Windows 7 SP1 package. Sourced.

SP1_X64_URL=http://download.windowsupdate.com/msdownload/update/software/svpk/2011/02/windows6.1-kb976932-x64_74865ef2562006e51d7f9333b4a8d45b7a749dab.exe
SP1_X64_SHA256=f4d1d418d91b1619688a482680ee032ffd2b65e420c6d2eaecf8aa3762aa64c8
SP1_X64_SIZE=947070088
GDIPLUS_PATH=amd64_microsoft.windows.gdiplus_6595b64144ccf1df_1.1.7601.17514_none_2b24536c71ed437a/gdiplus.dll
GDIPLUS_SHA256=980ea189929d95eb36e35980fff0c81f7b78de9422771fde8f4ac7a779f5bd89
# The only byte ranges cabextract reads to get gdiplus.dll out of the 947 MB package
# (offset:length): 71 MB instead of the whole file. Anything else stays a sparse hole.
SP1_X64_RANGES=(0:15814656 126373888:54716060 936325120:36864 947052544:17544)

sp1_x64_partial() {  # sp1_x64_partial DEST — fetch just the ranges above into a sparse file
    local dest=$1 r start len
    rm -f "$dest"
    truncate -s "$SP1_X64_SIZE" "$dest"
    for r in "${SP1_X64_RANGES[@]}"; do
        start=${r%:*} len=${r#*:}
        curl -fsSL --retry 3 -r "$start-$((start + len - 1))" "$SP1_X64_URL" |
            dd of="$dest" bs=1M oflag=seek_bytes seek="$start" conv=notrunc status=none ||
            return 1
    done
}

gdiplus_dll() {  # gdiplus_dll DIR — extract the verified gdiplus.dll into DIR
    local dir=$1 full="${XDG_CACHE_HOME:-$HOME/.cache}/winetricks/win7sp1/windows6.1-KB976932-X64.exe"
    local part="$CACHE_DIR/win7sp1-x64-partial.exe" src
    if [[ -f "$CACHE_DIR/gdiplus.dll" ]] && sha256sum "$CACHE_DIR/gdiplus.dll" | grep -q "^$GDIPLUS_SHA256 "; then
        cp "$CACHE_DIR/gdiplus.dll" "$dir/gdiplus.dll"; return 0
    fi
    if [[ -f "$full" ]] && sha256sum "$full" | grep -q "^$SP1_X64_SHA256 "; then
        src=$full                                         # already downloaded by winetricks
    else
        say "Downloading Microsoft GDI+ (about 70 MB of the Windows 7 SP1 package)"
        sp1_x64_partial "$part" || die "download failed: $SP1_X64_URL"
        src=$part
    fi
    cabextract -q -d "$dir" -F "$GDIPLUS_PATH" "$src" 2>/dev/null
    rm -f "$part"
    sha256sum "$dir/$GDIPLUS_PATH" 2>/dev/null | grep -q "^$GDIPLUS_SHA256 " ||
        die "gdiplus.dll extraction failed or checksum mismatch"
    mv "$dir/$GDIPLUS_PATH" "$dir/gdiplus.dll"
    cp "$dir/gdiplus.dll" "$CACHE_DIR/gdiplus.dll"
}

install_gdiplus() {  # install_gdiplus PREFIX REG
    local pfx=$1 reg=$2 tmp
    say "Installing Microsoft GDI+ (smooth, anti-aliased Adobe UI drawing)"
    tmp=$(mktemp -d)
    gdiplus_dll "$tmp"
    cp -f "$tmp/gdiplus.dll" "$pfx/drive_c/windows/system32/gdiplus.dll"
    rm -rf "$tmp"
    # 64-bit only; 32-bit programs fall back to Wine's builtin.
    printf '\r\n[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]\r\n"gdiplus"="native,builtin"\r\n' >> "$reg"
}
