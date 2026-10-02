#!/usr/bin/env bash
# Developer helper: start a hidden X display (default :77) with Muffin as window manager,
# for testing Wine programs without touching the real desktop. Idempotent.
#   dev/hidden-display.sh [:N]
set -u
disp=${1:-${HIDDEN_DISPLAY:-:77}}
logs=${XDG_RUNTIME_DIR:-/tmp}/adobe-wine-hidden
mkdir -p "$logs"
if ! pgrep -f "Xvfb $disp " >/dev/null; then
    setsid nohup Xvfb "$disp" -screen 0 1920x1080x24 -dpi 96 +extension GLX > "$logs/xvfb.log" 2>&1 &
    sleep 1
fi
if ! pgrep -f "muffin --replace --display=$disp" >/dev/null; then
    # Own D-Bus session: a second Muffin on the user's bus would take over its services.
    setsid nohup dbus-run-session -- muffin --replace --display="$disp" --sm-disable > "$logs/muffin.log" 2>&1 &
    sleep 2
fi
pgrep -af "Xvfb $disp |muffin --replace --display=$disp" | grep -v dbus-run-session
