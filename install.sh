#!/usr/bin/env bash
# Install "After Effects on Linux": a patched Proton-CachyOS runner (or a Wine you choose),
# the tools in bin/ and lib/, then set up every Wine prefix holding an After Effects / Media
# Encoder install (or a fresh prefix to install into). Opened from a file manager, or with
# --gui, it starts the graphical installer (lib/installer/), which runs this script.
#
#   ./install.sh [OPTIONS]
#     --gui                   graphical installer
#     --prefix DIR            Wine prefix for the Adobe apps
#     --runner-dir DIR        where the patched Wine is downloaded (~1 GB unpacked)
#     --wine DIR              use another Wine instead (DIR holds bin/wine; /usr = the
#                             system's); this project's Wine fixes then do not apply
#     --patched-wine          back to the patched Wine
#     --adobe-installer FILE  run this Adobe installer (Set-up.exe) when setup is done
#     --no-nvidia --no-theme --no-menu --no-exe-handler   (see lib/paths.sh)
#     --no-setup              install or update the runner and tools only
#     --missing-packages      list the Debian/Ubuntu packages still needed, then exit
# Choices are saved in ~/.config/adobe-wine/config and reused by later runs.
set -euo pipefail
repo=$(dirname "$(readlink -f "$0")")
LIB_DIR=$repo/lib

if [[ "${1:-}" == --gui || ( $# -eq 0 && ! -t 0 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ) ]]; then
    if python3 -c 'import gi; gi.require_version("Gtk", "4.0")' 2>/dev/null; then
        exec python3 "$LIB_DIR/installer/main.py" "$repo"
    fi
    msg="The installer window needs GTK 4 for Python. Install it with:\n\n  sudo apt install python3-gi gir1.2-gtk-4.0\n\nthen open install.sh again."
    zenity --error --width=440 --title="After Effects on Linux" --text="$msg" 2>/dev/null || printf '%b\n' "$msg" >&2
    exit 1
fi

# shellcheck source=lib/common.sh
source "$LIB_DIR/common.sh"

missing_packages() {  # Debian/Ubuntu package names of what is not installed yet
    local cmd pkg mod
    while read -r cmd pkg; do command -v "$cmd" >/dev/null || echo "$pkg"; done <<'EOF'
python3 python3
curl curl
xz xz-utils
cabextract cabextract
unzip unzip
zenity zenity
xdg-mime xdg-utils
update-mime-database shared-mime-info
fc-scan fontconfig
EOF
    while read -r mod pkg; do python3 -c "import $mod" 2>/dev/null || echo "$pkg"; done <<'EOF'
gi python3-gi
Xlib python3-xlib
cairo python3-gi-cairo
PIL python3-pil
cryptography.x509 python3-cryptography
EOF
}

setup=1 adobe_installer=
while (($#)); do
    case "$1" in
        --prefix) ADOBE_WINE_DEFAULT_PREFIX=$(readlink -m "$2"); shift ;;
        --runner-dir) ADOBE_WINE_RUNNER_DIR=$(readlink -m "$2"); shift ;;
        --wine) ADOBE_WINE_RUNNER=$(readlink -m "$2"); shift ;;
        --patched-wine) ADOBE_WINE_RUNNER= ;;
        --adobe-installer) adobe_installer=$(readlink -f "$2"); shift ;;
        --no-nvidia) ADOBE_WINE_NVIDIA=0 ;;
        --no-theme) ADOBE_WINE_THEME=0 ;;
        --no-menu) ADOBE_WINE_MENU=0 ;;
        --no-exe-handler) ADOBE_WINE_EXE_HANDLER=0 ;;
        --no-setup) setup= ;;
        --missing-packages) missing_packages; exit 0 ;;
        *) die "unknown option: $1 (the options are listed at the top of install.sh)" ;;
    esac
    shift
done

[[ $(uname -m) == x86_64 ]] || die "x86_64 Linux is required"
mapfile -t missing < <(missing_packages)
if ((${#missing[@]})); then
    die "missing packages. Install them with:  sudo apt install ${missing[*]}"
fi

# Save the choices (later runs, adobe-wine and ae-linux read them), then load them back.
mkdir -p "$(dirname "$ADOBE_WINE_CONFIG")"
{
    echo '# After Effects on Linux: written by install.sh (see lib/paths.sh)'
    printf 'ADOBE_WINE_RUNNER_DIR=%q\n' "${ADOBE_WINE_RUNNER_DIR:-$ADOBE_WINE_HOME/runner}"
    printf 'ADOBE_WINE_RUNNER=%q\n' "${ADOBE_WINE_RUNNER:-}"
    printf 'ADOBE_WINE_DEFAULT_PREFIX=%q\n' "${ADOBE_WINE_DEFAULT_PREFIX:-$ADOBE_WINE_HOME/prefix}"
    printf 'ADOBE_WINE_NVIDIA=%s\nADOBE_WINE_THEME=%s\n' "${ADOBE_WINE_NVIDIA:-1}" "${ADOBE_WINE_THEME:-1}"
    printf 'ADOBE_WINE_MENU=%s\nADOBE_WINE_EXE_HANDLER=%s\n' "${ADOBE_WINE_MENU:-1}" "${ADOBE_WINE_EXE_HANDLER:-1}"
} > "$ADOBE_WINE_CONFIG"
unset ADOBE_WINE_RUNNER_DIR ADOBE_WINE_RUNNER ADOBE_WINE_DEFAULT_PREFIX
# shellcheck source=lib/paths.sh
source "$LIB_DIR/paths.sh"

if ! runner_is_patched; then
    say "Wine: $RUNNER_FILES (not the patched runner: this project's Wine fixes do not apply)"
    [[ -x "$WINE_BIN" ]] || die "no Wine at $WINE_BIN"
else
    say "Wine runner (Proton-CachyOS 11.0, patched for Adobe apps) -> $RUNNER_DIR"
    if ! grep -qs 'cachyos-11.0-20260703' "$RUNNER_DIR/version"; then
        download "$RUNNER_URL" "$RUNNER_SHA256" "$CACHE_DIR/$RUNNER_NAME.tar.xz"
        say "Unpacking the runner"
        mkdir -p "$(dirname "$RUNNER_DIR")"
        tmp=$(mktemp -d "$RUNNER_DIR.new.XXXX")
        tar -xJf "$CACHE_DIR/$RUNNER_NAME.tar.xz" -C "$tmp"
        [[ -d "$RUNNER_DIR" ]] && mv "$RUNNER_DIR" "$RUNNER_DIR.old-$(date +%Y%m%d%H%M%S)"
        mv "$tmp"/*/ "$RUNNER_DIR"
        rmdir "$tmp"
    fi
    say "Applying the Adobe fixes to the runner"
    python3 "$LIB_DIR/patch_runner.py" "$RUNNER_DIR/files"
fi

say "Tools -> $APP_DIR"
rm -rf "$APP_DIR.new"
mkdir -p "$APP_DIR.new"
# install.sh and prebuilt/ too: the menu's setup window can run the installer again
cp -a "$repo/bin" "$repo/lib" "$repo/share" "$repo/prebuilt" "$repo/install.sh" "$repo/uninstall.sh" \
    "$APP_DIR.new/"
zig=${ZIG:-$(command -v zig || true)}
if [[ -n "$zig" && -d "$repo/src" ]]; then
    ZIG="$zig" "$repo/src/filedialog/build.sh" "$APP_DIR.new/filedialog.dll" >/dev/null
    ZIG="$zig" "$repo/src/reveal/build.sh" "$APP_DIR.new/winereveal.exe" >/dev/null
else
    cp "$repo/prebuilt/filedialog.dll" "$repo/prebuilt/winereveal.exe" "$APP_DIR.new/"
fi
if [[ "$(readlink -f "$repo")" == "$(readlink -f "$APP_DIR")" ]]; then
    # re-run from the installed copy: keep running files in place, swap afterwards
    rm -rf "$APP_DIR.old" && mv "$APP_DIR" "$APP_DIR.old" && mv "$APP_DIR.new" "$APP_DIR"
else
    rm -rf "$APP_DIR"
    mv "$APP_DIR.new" "$APP_DIR"
fi
mkdir -p "$BIN_DIR" "$APPS_DIR"
for b in adobe-wine adobe-wine-open ae-linux ae-linux-gui; do ln -sf "$APP_DIR/bin/$b" "$BIN_DIR/$b"; done
cat > "$APPS_DIR/ae-linux-setup.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=After Effects Linux Setup
Comment=Install or set up Adobe After Effects / Media Encoder under Wine
Exec=$BIN_DIR/ae-linux-gui
Icon=system-software-install
Terminal=false
Categories=AudioVideo;Video;Settings;
EOF
rm -rf "$ADOBE_WINE_HOME/tools"           # layout before app/ existed

if [[ -n "$setup" ]]; then
    "$BIN_DIR/ae-linux" setup
fi
if [[ -n "$adobe_installer" ]]; then
    "$BIN_DIR/ae-linux" install-app "$adobe_installer" "$DEFAULT_PREFIX"
fi
say "Installed. Run 'After Effects Linux Setup' from the menu (or: ae-linux gui) any time."
