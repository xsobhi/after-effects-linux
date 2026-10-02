#!/usr/bin/env bash
# Remove the tools, menu entries and file associations installed by install.sh.
# Wine prefixes (your installed Adobe apps and their settings) and the runner are kept
# unless --all is given.
set -euo pipefail
LIB_DIR=$(dirname "$(readlink -f "$0")")/lib
# shellcheck source=lib/common.sh
source "$LIB_DIR/common.sh"
data=${XDG_DATA_HOME:-$HOME/.local/share}

for b in adobe-wine adobe-wine-open ae-linux ae-linux-gui; do
    [[ -L "$BIN_DIR/$b" ]] && rm -f "$BIN_DIR/$b"
done
for f in "$APPS_DIR"/adobe-wine-*.desktop; do
    [[ -e "$f" ]] || continue
    script=$(sed -n 's/^Exec="\([^"]*\)".*/\1/p' "$f")
    [[ -n "$script" && -f "$script" ]] && grep -q 'adobe-wine' "$script" && rm -f "$script"
    rm -f "$f"
done
rm -f "$APPS_DIR/ae-linux-setup.desktop" "$data"/icons/hicolor/256x256/apps/adobe-wine-*
rm -f "$data/mime/packages/adobe-wine.xml"
update-mime-database "$data/mime" 2>/dev/null || true
update-desktop-database "$APPS_DIR" 2>/dev/null || true
rm -rf "$APP_DIR"
say "Removed the tools and menu entries."

if [[ "${1:-}" == --all ]]; then
    read -r -p "Also delete the runner and the default prefix $DEFAULT_PREFIX (installed Adobe apps)? [y/N] " answer
    if [[ "$answer" == [yY] ]]; then
        stop_prefix "$DEFAULT_PREFIX"
        rm -rf "$RUNNER_DIR" "$DEFAULT_PREFIX"
        say "Deleted the runner and the default prefix."
    fi
fi
