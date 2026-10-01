#!/usr/bin/env bash
# Developer helper: run an Adobe app on a hidden Xvfb display (default :77) at idle priority.
#   dev/ae-hidden.sh LOGFILE [EXE] [WINEDEBUG]
set -u
log=$1
exe=${2:-"$HOME/.local/share/adobe-wine/prefix/drive_c/Program Files/Adobe/Adobe After Effects 2020/Support Files/AfterFX.exe"}
export DISPLAY=${HIDDEN_DISPLAY:-:77} ADOBE_WINE_NO_OFFLOAD=1 WINEDEBUG=${3:--all}
cd "$(dirname "$exe")"
nice -n 19 ionice -c3 "$HOME/.local/bin/adobe-wine" "$exe" > "$log" 2>&1
