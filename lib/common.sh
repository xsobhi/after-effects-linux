# Shared settings for install.sh and ae-linux (sourced, not executed).
# shellcheck shell=bash

ADOBE_WINE_HOME="${ADOBE_WINE_HOME:-$HOME/.local/share/adobe-wine}"
RUNNER_DIR="$ADOBE_WINE_HOME/runner"
DEFAULT_PREFIX="$ADOBE_WINE_HOME/prefix"
APP_DIR="$ADOBE_WINE_HOME/app"       # installed copy of this repo (bin, lib, share)
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/adobe-wine"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
export ADOBE_WINE_FONTFIX=1  # setup registers fonts itself: adobe-wine skips its font check

# Proton-CachyOS build the binary patches in lib/patch_runner.py were made for.
RUNNER_NAME="proton-cachyos-11.0-20260703-slr-x86_64"
RUNNER_URL="https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-11.0-20260703-slr/$RUNNER_NAME.tar.xz"
RUNNER_SHA256="62ff4b2750180723cc00538608fe687e21d1d91a31ef64ce1a7c9f46c3db310b"

WINETRICKS_VERSION="20260125"
WINETRICKS_URL="https://raw.githubusercontent.com/Winetricks/winetricks/$WINETRICKS_VERSION/src/winetricks"
WINETRICKS_SHA256="431f82fc74000e6c864409f1d8fb495d696c03928808e3e8acffc45179312a7b"

# CLSID_FileOpenDialog / CLSID_FileSaveDialog, served by filedialog.dll.
FILEDIALOG_CLSIDS=("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}" "{C0B4E2F3-BA21-4773-8DBA-335EC946EB8B}")

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# download URL SHA256 DEST — reuses a cached copy when its hash matches.
download() {
    local url=$1 sha=$2 dest=$3
    if [[ -f "$dest" ]] && sha256sum "$dest" | grep -q "^$sha "; then
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    curl -fL --retry 3 -C - -o "$dest.part" "$url" || die "download failed: $url"
    sha256sum "$dest.part" | grep -q "^$sha " || { rm -f "$dest.part"; die "checksum mismatch: $url"; }
    mv "$dest.part" "$dest"
}

wine_in() {  # wine_in PREFIX ARGS... — run the patched runner in a given prefix
    ADOBE_WINE_PREFIX="$1" "$BIN_DIR/adobe-wine" "${@:2}"
}

stop_prefix() {
    WINEPREFIX="$1" "$RUNNER_DIR/files/bin/wineserver" -k 2>/dev/null || true
    WINEPREFIX="$1" timeout 30s "$RUNNER_DIR/files/bin/wineserver" -w 2>/dev/null || true
}
