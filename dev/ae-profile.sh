#!/usr/bin/env bash
# Profile a running Adobe app while you repeat the slow action (e.g. drag-selecting text):
# CPU per thread (and of the X server, wineserver and the compositor), plus stack samples
# of the app's main thread. Report goes to the terminal and ~/.local/share/adobe-wine/logs/.
#   dev/ae-profile.sh [SECONDS] [EXE]          (defaults: 15 AfterFX.exe)
set -euo pipefail
secs=${1:-15} exe=${2:-AfterFX.exe}
here=$(dirname "$(readlink -f "$0")")
cache=${XDG_CACHE_HOME:-$HOME/.cache}/adobe-wine-build
snap="$cache/stacksnap.exe"
out="$HOME/.local/share/adobe-wine/logs/profile-$(date +%m%d-%H%M%S)"
support="$HOME/.local/share/adobe-wine/prefix/drive_c/Program Files/Adobe"
mkdir -p "$cache" "$(dirname "$out")"
if [[ ! -f "$snap" || "$here/stacksnap.c" -nt "$snap" ]]; then
    zig=${ZIG:-$(command -v zig || ls "$cache"/zig-*/zig 2>/dev/null | head -1)}
    "$zig" cc -target x86_64-windows-gnu -O2 -o "$snap" "$here/stacksnap.c" -ldbghelp
fi
pid=$(pgrep -f "^C:.*\\\\$exe" | head -1) || { echo "$exe is not running" >&2; exit 1; }

cpu() {  # "tid name ticks" for every thread of the app and a few desktop processes
    local p t
    for t in /proc/"$pid"/task/*; do
        printf '%s %s %s\n' "${t##*/}" "$(tr ' ' _ < "$t/comm")" "$(awk '{print $14 + $15}' "$t/stat")"
    done
    for p in $(pgrep -x Xorg) $(pgrep -x wineserver) $(pgrep -x cinnamon) $(pgrep -x muffin); do
        printf '%s %s %s\n' "p$p" "[$(cat /proc/"$p"/comm)]" "$(awk '{print $14 + $15}' /proc/"$p"/stat)"
    done
}

printf 'Profiling %s (pid %s) for %ss: repeat the slow action now.\n' "$exe" "$pid" "$secs"
cpu > "$out.cpu0"
"$HOME/.local/bin/adobe-wine" "$snap" "$exe" "$secs" 10 > "$out.samples" 2> "$out.err" || true
cpu > "$out.cpu1"
{
    printf '== CPU over %ss (%% of one core)\n' "$secs"
    join <(sort "$out.cpu0") <(sort "$out.cpu1") |
        awk -v s="$secs" -v hz="$(getconf CLK_TCK)" -v main="$pid" '
            { d = ($5 - $3) * 100 / (s * hz); if (d >= 1) printf "%6.1f%%  %s %s%s\n", d, $1, $2, ($1 == main ? "  (main)" : "") }' |
        sort -rn | head -15
    echo
    python3 "$here/profile_report.py" "$out.samples" "$support" \
        "$HOME/.local/share/adobe-wine/runner/files/lib/wine/x86_64-windows"
} | tee "$out.txt"
rm -f "$out.cpu0" "$out.cpu1"
printf '\nSaved: %s.txt\n' "$out"
