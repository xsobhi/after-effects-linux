#!/usr/bin/env bash
# Build winereveal.exe (x86_64 Windows) with Zig's bundled clang + mingw-w64 headers.
#   ZIG=/path/to/zig ./build.sh [output.exe]
set -euo pipefail
cd "$(dirname "$0")"
zig="${ZIG:-zig}"
out="${1:-winereveal.exe}"
"$zig" cc -target x86_64-windows-gnu -O2 -municode -Wl,--subsystem,windows -Wall -Wno-unused-parameter \
    -o "$out" reveal.c
rm -f "${out%.exe}.lib" "${out%.exe}.pdb"
printf 'built %s\n' "$out"
