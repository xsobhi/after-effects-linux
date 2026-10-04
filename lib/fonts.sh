# shellcheck shell=bash
# Desktop fonts in the Adobe prefix: checks cheap enough for every program start (sourced by
# adobe-wine) and the repairs behind them (sourced by prefix_setup.sh).
#
# Wine lists the fonts fontconfig knows (~/.local/share/fonts, /usr/share/fonts) next to
# C:\windows\Fonts, so fonts installed on the desktop reach Adobe's font menus. Three things
# got in the way:
#  - Wine's FontSubstitutes (from wine.inf, re-applied on every prefix update) map
#    "Helvetica" to Arial, "Times" to Times New Roman, ... Enumerating such a family gives
#    the substitute's faces, so Adobe's font list never saw an installed Helvetica.
#  - Adobe's CoolType keeps its list of OS fonts (AdobeFnt_OSFonts.lst) and only adds new
#    names: when a font of the same name replaced another one (Microsoft's Tahoma over
#    Wine's), the menu kept the old entry, so projects asking for the real one found it
#    missing.
#  - Proton's look-alikes of Windows fonts were linked into C:\windows\Fonts even when the
#    real Microsoft font was installed on the desktop (see link_runner_fonts).

fonts_signature() {  # which font files fontconfig has, and their versions
    fc-list --format '%{file} %{fontversion}\n' 2>/dev/null | LC_ALL=C sort | md5sum | cut -d' ' -f1
}

font_substitutes() {  # font_substitutes PREFIX — the names FontSubstitutes maps elsewhere
    awk '/^\[Software\\\\Microsoft\\\\Windows NT\\\\CurrentVersion\\\\FontSubstitutes\]/ {k = 1; next}
         k && /^\[/ {exit}
         k && /^"/ {n = $0; sub(/^"/, "", n); sub(/"=.*/, "", n); print n}' "$1/system.reg"
}

shadowed_substitutes() {  # shadowed_substitutes PREFIX — substitutes hiding an installed family
    font_substitutes "$1" | awk -F, 'NR == FNR {installed[$0]; next} $1 in installed' \
        <(fc-list --format '%{family}\n' 2>/dev/null | tr ',' '\n') -
}

fonts_need_update() {  # fonts_need_update PREFIX — true if `ae-linux fonts` has work to do
    local pfx=$1
    [[ -f "$pfx/system.reg" ]] || return 1
    # DirectWrite's last-resort font gone from the registry list (Direct2D apps draw no text)
    awk '/^\[Software\\\\Microsoft\\\\Windows NT\\\\CurrentVersion\\\\Fonts\]/ {k = 1; next}
         k && /^\[/ {exit 1}  k && /^"Tahoma \(TrueType\)"=/ {exit 0}  END {if (!k) exit 1}' \
        "$pfx/system.reg" || return 0
    [[ "$(cat "$pfx/.adobe-wine-fonts" 2>/dev/null)" == "$(fonts_signature)" ]] || return 0
    [[ -n "$(shadowed_substitutes "$pfx")" ]]
}
