#!/usr/bin/env python3
"""Make Wine's own UI (menus, dialogs, captions, scrollbars) follow the desktop theme.

Reads the current GTK theme colours and UI font (Cinnamon, then GNOME settings) and
writes a .reg file with those colours. With --msstyles, controls are drawn by that visual
style (built from the GTK theme by msstyles/build.py); otherwise Wine's flat "classic"
rendering is used.
Usage: theme.py OUTPUT.reg [--msstyles C:\\path\\to\\theme.msstyles]
"""
import os
import re
import struct
import subprocess
import sys


def gsetting(schema, key):
    try:
        out = subprocess.run(['gsettings', 'get', schema, key], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.strip("'") if out else None


def desktop_setting(key, schemas=('org.cinnamon.desktop.interface', 'org.gnome.desktop.interface')):
    for schema in schemas:
        value = gsetting(schema, key)
        if value:
            return value
    return None


def theme_css(name):
    for base in (os.path.expanduser('~/.themes'), os.path.expanduser('~/.local/share/themes'),
                 '/usr/share/themes'):
        path = os.path.join(base, name, 'gtk-3.0', 'gtk.css')
        if os.path.exists(path):
            with open(path, encoding='utf-8', errors='replace') as f:
                return f.read()
    return ''


def parse_color(value, bg=(255, 255, 255)):
    value = value.strip()
    m = re.fullmatch(r'#([0-9a-fA-F]{6})', value)
    if m:
        return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r'rgba?\(([^)]*)\)', value)
    if m:
        parts = [float(p) for p in m.group(1).split(',')]
        alpha = parts[3] if len(parts) > 3 else 1.0
        return tuple(round(c * alpha + b * (1 - alpha)) for c, b in zip(parts[:3], bg))
    m = re.fullmatch(r'alpha\((white|black),\s*([0-9.]+)\)', value)
    if m:
        c = 255 if m.group(1) == 'white' else 0
        a = float(m.group(2))
        return tuple(round(c * a + b * (1 - a)) for b in bg)
    return None


def css_prop(css, selector, prop):
    """PROP of the first rule whose selector list contains SELECTOR exactly."""
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        if selector in (sel.strip() for sel in m.group(1).split(',')):
            value = re.search(r'(?:^|;)\s*' + re.escape(prop) + r'\s*:\s*([^;]+)', m.group(2))
            if value:
                return value.group(1).strip()
    return ''


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def palette(css, dark_hint):
    defs = dict(re.findall(r'@define-color\s+(\w+)\s+([^;]+);', css))
    fallback_bg = (46, 46, 51) if dark_hint else (240, 240, 242)
    bg = parse_color(defs.get('theme_bg_color', '')) or fallback_bg
    dark = sum(bg) / 3 < 128

    def get(name, default):
        return parse_color(defs.get(name, ''), bg) or default

    fg = get('theme_fg_color', (228, 228, 228) if dark else (32, 32, 32))
    accent = get('theme_selected_bg_color', (31, 158, 222))
    sel_fg = get('theme_selected_fg_color', (255, 255, 255))
    border = get('borders', mix(bg, (0, 0, 0), 0.3))
    wm_bg = get('wm_bg', mix(bg, (0, 0, 0), 0.25) if dark else bg)
    wm_bg_inactive = get('wm_bg_unfocused', wm_bg)
    wm_border = get('wm_border', border)
    disabled = get('insensitive_fg_color', mix(fg, bg, 0.5))
    edge = (255, 255, 255) if dark else (0, 0, 0)
    field = mix(bg, (0, 0, 0), 0.12) if dark else get('theme_base_color', (255, 255, 255))
    # Menus as GTK draws them: own bar/popup backgrounds and a subtle hover, not the accent.
    menu_bg = parse_color(css_prop(css, 'menu', 'background-color'), bg) or bg
    menubar_bg = parse_color(css_prop(css, 'menubar', 'background-color'), bg) or bg
    menu_hover = parse_color(css_prop(css, 'menu menuitem:hover', 'background-color'), menu_bg) or accent
    colors = {
        'Background': wm_bg, 'AppWorkSpace': wm_bg_inactive, 'Window': field,
        'WindowText': fg, 'WindowFrame': wm_border, 'ButtonFace': bg, 'ButtonText': fg,
        'ButtonAlternateFace': bg, 'ButtonHilight': mix(bg, edge, 0.10),
        'ButtonLight': mix(bg, edge, 0.05), 'ButtonShadow': border,
        'ButtonDkShadow': mix(border, (0, 0, 0), 0.25), 'GrayText': disabled,
        'Hilight': accent, 'HilightText': sel_fg, 'HotTrackingColor': accent,
        'Menu': menu_bg, 'MenuBar': menubar_bg, 'MenuText': fg, 'MenuHilight': menu_hover,
        'Scrollbar': mix(bg, (0, 0, 0), 0.08), 'InfoWindow': mix(bg, (0, 0, 0), 0.35),
        'InfoText': fg, 'ActiveTitle': wm_bg, 'GradientActiveTitle': wm_bg,
        'InactiveTitle': wm_bg_inactive, 'GradientInactiveTitle': wm_bg_inactive,
        'TitleText': fg, 'InactiveTitleText': mix(fg, wm_bg_inactive, 0.45),
        'ActiveBorder': wm_border, 'InactiveBorder': wm_border,
    }
    return colors, dark


def logfont(face, height, weight=400):
    name = face.encode('utf-16-le')[:62].ljust(64, b'\0')
    # lfHeight lfWidth lfEscapement lfOrientation lfWeight, then 8 BYTE fields
    # (CLEARTYPE_QUALITY = 5, DEFAULT_PITCH|FF_SWISS = 0x20), then lfFaceName[32].
    return struct.pack('<5i8B', height, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 5, 0x20) + name


def split_font(spec, default=('Noto Sans', 10.0)):
    m = re.fullmatch(r'(.+?)\s+([0-9.]+)', spec or '')
    return (m.group(1), float(m.group(2))) if m else default


def reg_hex(data):
    return 'hex:' + ','.join(f'{b:02x}' for b in data)


def build(out_path, msstyles=None):
    gtk_theme = desktop_setting('gtk-theme') or 'Adwaita'
    scheme = gsetting('org.x.apps.portal', 'color-scheme') or \
        gsetting('org.gnome.desktop.interface', 'color-scheme') or ''
    colors, dark = palette(theme_css(gtk_theme), 'dark' in scheme or 'dark' in gtk_theme.lower())
    face, size = split_font(desktop_setting('font-name'))
    title_face, _ = split_font(gsetting('org.cinnamon.desktop.wm.preferences', 'titlebar-font')
                               or gsetting('org.gnome.desktop.wm.preferences', 'titlebar-font'),
                               (face, size))
    title_weight = 500 if 'Medium' in title_face else 700 if 'Bold' in title_face else 400
    title_face = re.sub(r'\s+(Medium|Bold|Regular)$', '', title_face)
    height = -round(size * 96 / 72)
    aa = gsetting('org.cinnamon.settings-daemon.plugins.xsettings', 'antialiasing') or 'rgba'
    order = gsetting('org.cinnamon.settings-daemon.plugins.xsettings', 'rgba-order') or 'rgb'

    lines = ['Windows Registry Editor Version 5.00', '',
             '[HKEY_CURRENT_USER\\Control Panel\\Colors]']
    lines += [f'"{k}"="{v[0]} {v[1]} {v[2]}"' for k, v in colors.items()]
    lines += ['', '[HKEY_CURRENT_USER\\Control Panel\\Desktop]',
              '"FontSmoothing"="2"',
              f'"FontSmoothingType"=dword:{2 if aa == "rgba" else 1:08x}',
              f'"FontSmoothingOrientation"=dword:{0 if order == "bgr" else 1:08x}',
              '"FontSmoothingGamma"=dword:00000578',
              # Windows defaults minus gradient captions (bit 0x10); flat menus stay on.
              '"UserPreferencesMask"=hex:8e,1e,07,80,12,00,00,00',
              '', '[HKEY_CURRENT_USER\\Control Panel\\Desktop\\WindowMetrics]']
    for key in ('MenuFont', 'StatusFont', 'MessageFont', 'IconFont'):
        lines.append(f'"{key}"={reg_hex(logfont(face, height))}')
    for key in ('CaptionFont', 'SmCaptionFont'):
        lines.append(f'"{key}"={reg_hex(logfont(title_face, height, title_weight))}')
    # Menu bar row like GTK's (text line + 4px padding top and bottom), in twips.
    lines += [f'"MenuHeight"="-{(round(size * 96 / 72 * 1.2) + 9) * 15}"',
              '', '[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager]',
              f'"ThemeActive"="{1 if msstyles else 0}"',
              ] + ([f'"DllName"="{msstyles.replace(chr(92), chr(92) * 2)}"', '"ColorName"="Blue"',
                    '"SizeName"="NormalSize"'] if msstyles else []) + [
              '', '[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize]',
              f'"AppsUseLightTheme"=dword:{0 if dark else 1:08x}',
              f'"SystemUsesLightTheme"=dword:{0 if dark else 1:08x}',
              '', '[HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\Replacements]',
              f'"Segoe UI"="{face}"', f'"Segoe UI Semibold"="{face}"',
              '', '[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes]',
              f'"MS Shell Dlg"="{face}"', f'"MS Shell Dlg 2"="{face}"', '']
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(lines))
    print(f'theme: {gtk_theme} ({"dark" if dark else "light"}), font {face} {size:g}pt')
    return dark


if __name__ == '__main__':
    if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != '--msstyles'):
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[3] if len(sys.argv) == 4 else None)
