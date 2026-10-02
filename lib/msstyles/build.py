#!/usr/bin/env python3
"""Build a Windows visual style (.msstyles) that matches the desktop's GTK theme.

  build.py BASE.msstyles OUT.msstyles [--no-gtk]

BASE is Wine's own Light theme (C:\\windows\\resources\\themes\\light\\light.msstyles in any
prefix): every control it defines is kept, its bitmaps and colours are recoloured to the
desktop palette, and the most visible controls (buttons, check boxes, radio buttons, combo
boxes, text fields, ...) are re-drawn by GTK itself (parts.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import pe_res  # noqa: E402
import recolor  # noqa: E402
import theme  # noqa: E402  (lib/theme.py: GTK theme detection and palette)


def desktop_palette():
    name = theme.desktop_setting('gtk-theme') or 'Adwaita'
    scheme = theme.gsetting('org.x.apps.portal', 'color-scheme') or \
        theme.gsetting('org.gnome.desktop.interface', 'color-scheme') or ''
    colors, dark = theme.palette(theme.theme_css(name), 'dark' in scheme or 'dark' in name.lower())
    pal = recolor.Palette(bg=colors['ButtonFace'], base=colors['Window'] if not dark else colors['ButtonFace'],
                          fg=colors['ButtonText'], disabled=colors['GrayText'],
                          border=colors['ButtonShadow'], accent=colors['Hilight'])
    return pal, name, dark


def _ini_codec(blob):
    if blob[:2] == b'\xff\xfe':
        return blob[2:].decode('utf-16-le'), b'\xff\xfe'
    if len(blob) > 1 and blob[1:2] == b'\0':
        return blob.decode('utf-16-le'), b''
    return blob.decode('latin-1'), None


def build(base, out, use_gtk=True):
    res = pe_res.read(base)
    pal, name, dark = desktop_palette()
    images, ini_edits = {}, {}
    for rname, langs in res[pe_res.RT_BITMAP].items():
        for lang, dib in langs.items():
            img, bpp = recolor.dib_to_image(dib)
            images[rname] = (lang, recolor.recolor_image(img, pal), bpp)
    if use_gtk:
        import parts
        ini_edits = parts.override(images, pal, name, dark)
    for rname, (lang, img, bpp) in images.items():
        res[pe_res.RT_BITMAP][rname] = {lang: recolor.image_to_dib(img, bpp)}
    for rname, langs in res['TEXTFILE'].items():
        for lang, blob in langs.items():
            text, bom = _ini_codec(blob)
            if rname == 'THEMES_INI':
                text = text.replace('DisplayName = Light', f'DisplayName = {name}')
            else:
                text = recolor.recolor_ini(text, pal)
                if ini_edits:
                    import parts
                    text = parts.apply_ini(text, ini_edits)
            langs[lang] = (bom + text.encode('utf-16-le')) if bom is not None else text.encode('latin-1')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pe_res.write(out, res)
    print(f'msstyles: {name} ({"dark" if dark else "light"}) -> {out}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 2:
        sys.exit(__doc__)
    build(args[0], args[1], '--no-gtk' not in sys.argv)
