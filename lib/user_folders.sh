#!/usr/bin/env bash
# Point the Windows user's Desktop, Documents, Downloads, Music, Pictures, Videos and
# Templates at the real Linux (XDG) folders, as plain Wine does; Proton keeps them inside
# the prefix, so Adobe apps never saw the user's files. Existing files are copied over
# without overwriting anything; empty folders are dropped.
# Usage: user_folders.sh PREFIX
set -euo pipefail
prefix=${1:?usage: user_folders.sh PREFIX}

link_folder() {  # windows_dir xdg_key
    local src=$1 target
    target=$(xdg-user-dir "$2" 2>/dev/null || true)
    [[ -n "$target" && "$target" != "$HOME" && "$target" != "$HOME/" ]] || return 0
    mkdir -p "$target"
    if [[ -L "$src" ]]; then
        [[ "$(readlink -f "$src")" == "$(readlink -f "$target")" ]] && return 0
        rm "$src"
    elif [[ -d "$src" ]]; then
        # Drop empty folders (Proton's placeholders, app skeletons recreated on demand).
        while find "$src" -mindepth 1 -type d -empty -print -quit | grep -q .; do
            find "$src" -mindepth 1 -type d -empty -delete
        done
        if find "$src" -mindepth 1 -print -quit | grep -q .; then
            cp -a -n "$src/." "$target/"
        fi
        rm -rf "$src"
    fi
    ln -s "$target" "$src"
    printf '  %s -> %s\n' "${src#"$prefix"/drive_c/}" "$target"
}

for user_dir in "$prefix"/drive_c/users/*/; do
    user_dir=${user_dir%/}
    [[ -L "$user_dir" || "${user_dir##*/}" == Public ]] && continue
    link_folder "$user_dir/Desktop" DESKTOP
    link_folder "$user_dir/Documents" DOCUMENTS
    link_folder "$user_dir/Downloads" DOWNLOAD
    link_folder "$user_dir/Music" MUSIC
    link_folder "$user_dir/Pictures" PICTURES
    link_folder "$user_dir/Videos" VIDEOS
    link_folder "$user_dir/Templates" TEMPLATES
done
