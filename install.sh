#!/usr/bin/env bash
# Install "After Effects on Linux": a patched Proton-CachyOS runner, the tools in bin/ and lib/,
# then set up every Wine prefix holding an After Effects / Media Encoder install
# (or a fresh prefix to install into).
#
#   ./install.sh              install or update, then set up prefixes
#   ./install.sh --no-setup   install or update the runner and tools only
set -euo pipefail
repo=$(dirname "$(readlink -f "$0")")
LIB_DIR=$repo/lib
# shellcheck source=lib/common.sh
source "$LIB_DIR/common.sh"

[[ $(uname -m) == x86_64 ]] || die "x86_64 Linux is required"
missing=()
need() { command -v "$1" >/dev/null || missing+=("$2"); }
need python3 python3; need curl curl; need xz xz-utils; need cabextract cabextract
need unzip unzip; need zenity zenity; need xdg-mime xdg-utils; need update-mime-database shared-mime-info
python3 -c 'import gi' 2>/dev/null || missing+=(python3-gi)
python3 -c 'import Xlib' 2>/dev/null || missing+=(python3-xlib)
python3 -c 'import cairo' 2>/dev/null || missing+=(python3-gi-cairo)
python3 -c 'import PIL' 2>/dev/null || missing+=(python3-pil)
python3 -c 'import cryptography.x509' 2>/dev/null || missing+=(python3-cryptography)
if ((${#missing[@]})); then
    die "missing packages. Install them with:  sudo apt install ${missing[*]}"
fi

say "Wine runner (Proton-CachyOS 11.0, patched for Adobe apps)"
if ! grep -qs 'cachyos-11.0-20260703' "$RUNNER_DIR/version"; then
    download "$RUNNER_URL" "$RUNNER_SHA256" "$CACHE_DIR/$RUNNER_NAME.tar.xz"
    tmp=$(mktemp -d "$ADOBE_WINE_HOME.runner.XXXX")
    tar -xJf "$CACHE_DIR/$RUNNER_NAME.tar.xz" -C "$tmp"
    [[ -d "$RUNNER_DIR" ]] && mv "$RUNNER_DIR" "$RUNNER_DIR.old-$(date +%Y%m%d%H%M%S)"
    mkdir -p "$ADOBE_WINE_HOME"
    mv "$tmp"/*/ "$RUNNER_DIR"
    rmdir "$tmp"
fi
python3 "$LIB_DIR/patch_runner.py" "$RUNNER_DIR/files"

say "Tools -> $APP_DIR"
rm -rf "$APP_DIR.new"
mkdir -p "$APP_DIR.new"
cp -a "$repo/bin" "$repo/lib" "$repo/share" "$APP_DIR.new/"
zig=${ZIG:-$(command -v zig || true)}
if [[ -n "$zig" ]]; then
    ZIG="$zig" "$repo/src/filedialog/build.sh" "$APP_DIR.new/filedialog.dll" >/dev/null
else
    cp "$repo/prebuilt/filedialog.dll" "$APP_DIR.new/filedialog.dll"
fi
rm -rf "$APP_DIR"
mv "$APP_DIR.new" "$APP_DIR"
mkdir -p "$BIN_DIR" "$APPS_DIR"
for b in adobe-wine adobe-wine-open ae-linux ae-linux-gui; do ln -sf "$APP_DIR/bin/$b" "$BIN_DIR/$b"; done
cat > "$APPS_DIR/ae-linux-setup.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=After Effects Linux Setup
Comment=Find Adobe After Effects / Media Encoder in Wine prefixes and set them up
Exec=$BIN_DIR/ae-linux-gui
Icon=system-software-install
Terminal=false
Categories=AudioVideo;Video;Settings;
EOF
rm -rf "$ADOBE_WINE_HOME/tools"           # layout before app/ existed

if [[ "${1:-}" != --no-setup ]]; then
    "$BIN_DIR/ae-linux" setup
fi
say "Installed. Run 'After Effects Linux Setup' from the menu (or: ae-linux gui) any time."
