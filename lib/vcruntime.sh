# shellcheck shell=bash
# Microsoft Visual C++ 2015-2022 runtime (+ MFC) for a prefix. Adobe apps need it.
# Under Proton the redistributable's own installer exits with status 17, so the DLLs are
# taken straight from Microsoft's signed packages (what winetricks already does for
# msvcp140). URLs and SHA-256 come from the pinned winetricks release. Sourced.

VC_DLLS=(concrt140 msvcp140 msvcp140_1 msvcp140_2 msvcp140_atomic_wait msvcp140_codecvt_ids
         vcamp140 vccorlib140 vcomp140 vcruntime140 vcruntime140_1 mfc140 mfc140u mfcm140 mfcm140u)

vc_redist() {  # vc_redist x86|x64 — path of the verified download
    local arch=$1 wt="$CACHE_DIR/winetricks-$WINETRICKS_VERSION" line url sha
    download "$WINETRICKS_URL" "$WINETRICKS_SHA256" "$wt"
    line=$(awk '/^load_vcrun2022\(\)/,/^}/' "$wt" | grep -m1 "w_download .*vc_redist.$arch.exe")
    url=$(awk '{print $2}' <<< "$line")
    sha=$(awk '{print $3}' <<< "$line")
    [[ -n "$url" && -n "$sha" ]] || die "could not find the vc_redist.$arch.exe pin in winetricks"
    download "$url" "$sha" "$CACHE_DIR/vc_redist-$sha.$arch.exe"
    printf '%s' "$CACHE_DIR/vc_redist-$sha.$arch.exe"
}

install_vcruntime() {  # install_vcruntime PREFIX REG
    local pfx=$1 reg=$2 win=$1/drive_c/windows tmp f
    say "Installing the Microsoft Visual C++ 2015-2022 runtime"
    tmp=$(mktemp -d)
    cabextract -q -d "$tmp/x86" "$(vc_redist x86)" 2>/dev/null
    cabextract -q -d "$tmp/x64" "$(vc_redist x64)" 2>/dev/null
    # x86: a10 = runtime, a11 = MFC.  x64: a12 = runtime, a13 = MFC (a11 is ARM64).
    # Files inside are named like msvcp140.dll_amd64.
    cabextract -q -d "$tmp/dll" "$tmp/x86/a10" "$tmp/x86/a11" "$tmp/x64/a12" "$tmp/x64/a13" 2>/dev/null
    # (Wine keeps placeholder DLLs under these names, so check the extracted files instead.)
    [[ -f "$tmp/dll/msvcp140.dll_x86" && -f "$tmp/dll/msvcp140.dll_amd64" ]] ||
        die "VC++ runtime extraction failed"
    for f in "$tmp"/dll/*.dll_x86; do cp -f "$f" "$win/syswow64/$(basename "${f%_x86}")"; done
    for f in "$tmp"/dll/*.dll_amd64; do cp -f "$f" "$win/system32/$(basename "${f%_amd64}")"; done
    rm -rf "$tmp"
    printf '\r\n[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]\r\n' >> "$reg"
    for f in "${VC_DLLS[@]}"; do printf '"%s"="native,builtin"\r\n' "$f"; done >> "$reg"
}
