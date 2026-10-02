#!/usr/bin/env bash
# Developer test for patches/0009: on<event> attributes set from script must become working
# event handlers (Adobe installer buttons). Loads dev/onclick-test.html in Wine's 64-bit and
# 32-bit iexplore on a hidden display, then clicks the page with a real (XTEST) mouse click.
#   dev/onclick-test.sh [PREFIX]    (default: a throwaway prefix in $TMPDIR; needs xdotool)
# ADOBE_WINE_HOME selects the runner (default ~/.local/share/adobe-wine).
set -u
here=$(cd "$(dirname "$0")" && pwd)
prefix=${1:-${TMPDIR:-/tmp}/adobe-wine-onclick-test}
port=${PORT:-8765}
work=$(mktemp -d)
trap 'kill $server 2>/dev/null; rm -rf "$work"' EXIT
cp "$here/onclick-test.html" "$work/"
"$here/hidden-display.sh" >/dev/null
export DISPLAY=${HIDDEN_DISPLAY:-:77} ADOBE_WINE_PREFIX=$prefix ADOBE_WINE_NO_OFFLOAD=1 WINEDEBUG=-all
aw="$here/../bin/adobe-wine"
wineserver="${ADOBE_WINE_HOME:-$HOME/.local/share/adobe-wine}/runner/files/bin/wineserver"
[[ -d "$prefix/drive_c" ]] || "$aw" wineboot -u >/dev/null 2>&1

# Serve the page; it POSTs its results to /result, appended to $work/result.txt.
python3 - "$work" "$port" <<'PY' &
import http.server, os, sys
root, port = sys.argv[1], int(sys.argv[2])
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=root, **k)
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
        with open(os.path.join(root, 'result.txt'), 'a') as f: f.write(body + '\n')
        self.send_response(200); self.send_header('Content-Length', '0'); self.end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
PY
server=$!
sleep 1

wait_for() { for _ in $(seq 1 40); do grep -q "$1" "$work/result.txt" 2>/dev/null && return 0; sleep 0.5; done; return 1; }
for arch in "64:Program Files" "32:Program Files (x86)"; do
    rm -f "$work/result.txt"
    "$aw" "C:\\${arch#*:}\\Internet Explorer\\iexplore.exe" "http://127.0.0.1:$port/onclick-test.html" \
        >/dev/null 2>&1 &
    ie=$!
    echo "== ${arch%%:*}-bit mshtml"
    if wait_for 'ready for click'; then
        win=$(xdotool search --name 'Wine Internet Explorer' | tail -1)
        eval "$(xdotool getwindowgeometry --shell "$win")"
        xdotool mousemove --sync $((X + WIDTH / 2)) $((Y + HEIGHT / 2)) click 1
        wait_for 'real mouse click' || echo 'FAIL real mouse click runs the handler' >> "$work/result.txt"
    fi
    grep -v 'ready for click' "$work/result.txt" 2>/dev/null || echo "(the page reported nothing)"
    WINEPREFIX=$prefix "$wineserver" -k
    wait "$ie" 2>/dev/null
done
