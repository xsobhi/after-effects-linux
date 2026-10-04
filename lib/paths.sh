# shellcheck shell=bash
# Where things live (sourced by common.sh and adobe-wine). Defaults below; the installer
# records the user's choices in ~/.config/adobe-wine/config (KEY="value" lines):
#   ADOBE_WINE_RUNNER_DIR      where the patched Proton-CachyOS runner is downloaded
#   ADOBE_WINE_RUNNER          the Wine to use: a directory holding bin/wine (default: the
#                              patched runner's files/; /usr for the system Wine)
#   ADOBE_WINE_DEFAULT_PREFIX  the Wine prefix Adobe apps are installed into
#   ADOBE_WINE_NVIDIA=0        do not render on the NVIDIA GPU of hybrid laptops
#   ADOBE_WINE_THEME=0         keep Wine's own look (no GTK colours/visual style)
#   ADOBE_WINE_MENU=0          no menu entries / .aep association
#   ADOBE_WINE_EXE_HANDLER=0   do not open .exe/.msi/.lnk/.bat files with this Wine
ADOBE_WINE_HOME="${ADOBE_WINE_HOME:-$HOME/.local/share/adobe-wine}"
ADOBE_WINE_CONFIG="${ADOBE_WINE_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/adobe-wine/config}"
# shellcheck source=/dev/null
[[ -f "$ADOBE_WINE_CONFIG" ]] && source "$ADOBE_WINE_CONFIG"
RUNNER_DIR="${ADOBE_WINE_RUNNER_DIR:-$ADOBE_WINE_HOME/runner}"
RUNNER_FILES="${ADOBE_WINE_RUNNER:-$RUNNER_DIR/files}"
DEFAULT_PREFIX="${ADOBE_WINE_DEFAULT_PREFIX:-$ADOBE_WINE_HOME/prefix}"
WINE_BIN="$RUNNER_FILES/bin/wine"
WINESERVER_BIN="$RUNNER_FILES/bin/wineserver"
if [[ ! -x "$WINESERVER_BIN" ]]; then         # distro Wine keeps it outside bin/
    WINESERVER_BIN=$(command -v wineserver || ls /usr/lib/wine/wineserver* 2>/dev/null | head -1 || true)
fi

runner_is_patched() {  # the Wine in use is this project's patched runner
    [[ "$(readlink -f "$RUNNER_FILES")" == "$(readlink -f "$RUNNER_DIR/files")" ]]
}
