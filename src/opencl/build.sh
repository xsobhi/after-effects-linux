#!/usr/bin/env bash
# Build Wine's OpenCL bridge (x86_64 opencl.so) against the system's libOpenCL.so.1.
# Proton-CachyOS 11.0 ships it built without OpenCL: every program sees no OpenCL device.
# The source is upstream Wine 11.0's dlls/opencl (same 86-entry unix call table as the
# runner's opencl.dll) and the Khronos OpenCL headers; both downloads are SHA-256 checked.
#   src/opencl/build.sh RUNNER_FILES_DIR OUTPUT.so     (needs gcc and libOpenCL.so.1)
set -euo pipefail
files=$1 out=$2
work=${XDG_CACHE_HOME:-$HOME/.cache}/adobe-wine-build/opencl
mkdir -p "$work"
fetch() {  # fetch URL SHA256 FILE
    [[ -f "$3" ]] && sha256sum "$3" | grep -q "^$2 " && return
    curl -fsSL -o "$3.part" "$1"
    sha256sum "$3.part" | grep -q "^$2 " || { echo "checksum mismatch: $1" >&2; exit 1; }
    mv "$3.part" "$3"
}
fetch https://dl.winehq.org/wine/source/11.0/wine-11.0.tar.xz \
    c07a6857933c1fc60dff5448d79f39c92481c1e9db5aa628db9d0358446e0701 "$work/wine-11.0.tar.xz"
fetch https://github.com/KhronosGroup/OpenCL-Headers/archive/refs/tags/v2024.10.24.tar.gz \
    159f2a550592bae49859fee83d372acd152328fdf95c0dcd8b9409f8fad5db93 "$work/OpenCL-Headers.tar.gz"
tar -xJf "$work/wine-11.0.tar.xz" -C "$work" wine-11.0/dlls/opencl wine-11.0/include
tar -xzf "$work/OpenCL-Headers.tar.gz" -C "$work"
printf '#define HAVE_CL_CL_H 1\n' > "$work/config.h"
lib=$(ls /usr/lib/x86_64-linux-gnu/libOpenCL.so.1 /usr/lib64/libOpenCL.so.1 /usr/lib/libOpenCL.so.1 2>/dev/null | head -1 || true)
[[ -n "$lib" ]] || { echo "libOpenCL.so.1 not found (Debian/Ubuntu: ocl-icd-libopencl1)" >&2; exit 1; }
w=$work/wine-11.0
gcc -O2 -fPIC -shared -o "$out" -I"$work" -I"$w/dlls/opencl" -I"$w/include" \
    -I"$work/OpenCL-Headers-2024.10.24" -D__WINESRC__ -DWINE_UNIX_LIB -D_REENTRANT \
    -fno-strict-aliasing -Wno-deprecated-declarations \
    "$w/dlls/opencl/unix_thunks.c" "$w/dlls/opencl/unix_wrappers.c" \
    "$files/lib/wine/x86_64-unix/ntdll.so" "$lib" -Wl,--no-undefined
strip "$out"
