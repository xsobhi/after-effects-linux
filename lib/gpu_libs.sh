# shellcheck shell=bash
# Install the runner's DXVK, vkd3d-proton and (on NVIDIA) NVAPI/CUDA/NVENC bridges into a
# prefix — what the Proton script does for Steam games. Sourced; needs lib/common.sh.
# DLL overrides are appended to the .reg file REG (imported once by prefix_setup.sh).

install_gpu_libs() {  # install_gpu_libs PREFIX REG
    local pfx=$1 reg=$2 lib=$RUNNER_FILES/lib/wine win=$1/drive_c/windows f
    if [[ ! -d "$lib/dxvk" || ! -d "$lib/vkd3d-proton" ]]; then
        warn "this Wine has no DXVK/vkd3d-proton (only Proton builds do): Direct3D stays Wine's own"
        return 0
    fi
    [[ -d "$lib/nvidia-libs" ]] || NVIDIA=
    say "Installing DXVK / vkd3d-proton${NVIDIA:+ / NVIDIA CUDA+NVAPI} into the prefix"
    for f in d3d8 d3d9 d3d10core d3d11 dxgi; do
        cp --remove-destination "$lib/dxvk/x86_64-windows/$f.dll" "$win/system32/$f.dll"
        cp --remove-destination "$lib/dxvk/i386-windows/$f.dll" "$win/syswow64/$f.dll"
    done
    for f in d3d12 d3d12core; do
        cp --remove-destination "$lib/vkd3d-proton/x86_64-windows/$f.dll" "$win/system32/$f.dll"
        cp --remove-destination "$lib/vkd3d-proton/i386-windows/$f.dll" "$win/syswow64/$f.dll"
    done
    local native=(d3d8 d3d9 d3d10core d3d11 dxgi d3d12 d3d12core) native_builtin=()
    if [[ -n "${NVIDIA:-}" ]]; then
        local nv=$lib/nvidia-libs
        cp --remove-destination "$nv/nvapi/x86_64-windows/nvapi64.dll" "$win/system32/nvapi64.dll"
        cp --remove-destination "$nv/nvapi/x86_64-windows/nvofapi64.dll" "$win/system32/nvofapi64.dll"
        cp --remove-destination "$nv/nvapi/i386-windows/nvapi.dll" "$win/syswow64/nvapi.dll"
        cp --remove-destination "$nv/nvcuda/x86_64-windows/nvcuda.dll.so" "$win/system32/nvcuda.dll"
        cp --remove-destination "$nv/nvcuda/i386-windows/nvcuda.dll.so" "$win/syswow64/nvcuda.dll"
        cp --remove-destination "$nv/nvenc/x86_64-windows/nvcuvid.dll.so" "$win/system32/nvcuvid.dll"
        cp --remove-destination "$nv/nvenc/x86_64-windows/nvencodeapi64.dll.so" "$win/system32/nvencodeapi64.dll"
        cp --remove-destination "$nv/nvenc/i386-windows/nvcuvid.dll.so" "$win/syswow64/nvcuvid.dll"
        cp --remove-destination "$nv/nvenc/i386-windows/nvencodeapi.dll.so" "$win/syswow64/nvencodeapi.dll"
        native+=(nvapi nvapi64 nvofapi64)
        native_builtin+=(nvcuda nvcuvid nvencodeapi nvencodeapi64)
    fi
    {
        printf '\r\n[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]\r\n'
        for f in "${native[@]}"; do printf '"%s"="native"\r\n' "$f"; done
        for f in "${native_builtin[@]}"; do printf '"%s"="native,builtin"\r\n' "$f"; done
    } >> "$reg"
}
