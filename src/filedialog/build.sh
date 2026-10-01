#!/usr/bin/env bash
# Build filedialog.dll (x86_64 Windows) with Zig's bundled clang + mingw-w64 headers.
#   ZIG=/path/to/zig ./build.sh [output.dll]
set -euo pipefail
cd "$(dirname "$0")"
zig="${ZIG:-zig}"
out="${1:-filedialog.dll}"
"$zig" cc -target x86_64-windows-gnu -O2 -shared -Wall -Wno-unused-parameter \
    -o "$out" main.c dialog.c results.c customize.c show.c fallback.c util.c filedialog.def \
    -lole32 -lshell32 -luuid -luser32
rm -f "${out%.dll}.lib" "${out%.dll}.pdb"
printf 'built %s\n' "$out"
