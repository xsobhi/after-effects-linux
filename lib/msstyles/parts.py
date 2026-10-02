"""Re-draw the most visible controls with GTK (see gtk_render.py) instead of recolouring
Wine's Light bitmaps: push buttons, check boxes, radio buttons, combo boxes, text fields
and group boxes. Also returns the ini changes the new images need (SizingMargins)."""
import re

import cairo
from PIL import Image

import gtk_render as g
import scrollbar

S = g.S
BUTTON = [('button', ['text-button'])]
COMBO = [('combobox', []), ('button', ['combo'])]
ENTRY = [('entry', [])]
FRAME = [('frame', []), ('border', [])]
PUSH_STATES = (0, S.PRELIGHT, S.ACTIVE | S.PRELIGHT, S.INSENSITIVE, S.FOCUSED, S.FOCUSED | S.PRELIGHT)
FIELD_STATES = (0, S.PRELIGHT, S.FOCUSED, S.INSENSITIVE)       # normal, hot, focused, disabled
BUTTON4 = (0, S.PRELIGHT, S.ACTIVE | S.PRELIGHT, S.INSENSITIVE)


def _check_states():
    states = []
    for base in (0, S.CHECKED, S.INCONSISTENT, 0, 0):   # unchecked, checked, mixed, implicit, excluded
        states += [base, base | S.PRELIGHT, base | S.ACTIVE | S.PRELIGHT, base | S.INSENSITIVE]
    return states


def _radio_states():
    return [b | s for b in (0, S.CHECKED) for s in (0, S.PRELIGHT, S.ACTIVE | S.PRELIGHT, S.INSENSITIVE)]


def chevron(w, h, rgb, count, colors=None):
    """count stacked w x h cells, each with a downward chevron (Mint's pan-down glyph)."""
    out = Image.new('RGBA', (w, h * count))
    for i in range(count):
        color = (colors[i] if colors else rgb)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * 4, h * 4)
        cr = cairo.Context(surf)
        cr.scale(4, 4)
        size = min(w * 0.7, h * 0.9, 9)
        cx, cy = w / 2, h / 2
        cr.set_source_rgba(*(c / 255 for c in color), 1)
        cr.set_line_width(max(1.2, size / 6))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.move_to(cx - size / 2, cy - size / 4)
        cr.line_to(cx, cy + size / 4)
        cr.line_to(cx + size / 2, cy - size / 4)
        cr.stroke()
        out.paste(g._image(surf, w, h), (0, i * h))
    return out


def override(images, pal, theme_name, dark):
    """Replace entries of images {RES_NAME: (lang, image, bpp)}; return ini edits."""
    g.use_theme(theme_name, dark)
    ini = {}

    def put(name, img):
        if name in images:
            images[name] = (images[name][0], img, 32)

    put('BLUE_BUTTON_BMP', g.stack([g.box(BUTTON, st, 24, 24) for st in PUSH_STATES]))
    ini['button.pushbutton'] = {'SizingMargins': '6, 6, 6, 6'}
    for name in images:
        m = re.fullmatch(r'BLUE_(CHECKBOX|RADIOBUTTON)_(\d+)PX_BMP', name)
        if m:
            size, kind = int(m.group(2)), 'check' if m.group(1) == 'CHECKBOX' else 'radio'
            states = _check_states() if kind == 'check' else _radio_states()
            put(name, g.stack([g.indicator(kind, st, size) for st in states]))
    put('BLUE_COMBOBOX_READONLY_BMP', g.stack([g.box(COMBO, st, 16, 24) for st in BUTTON4]))
    ini['combobox.readonly'] = {'SizingMargins': '5, 5, 5, 5'}
    for side in ('', '_RIGHT', '_LEFT'):    # dropdown buttons: only the glyph, as in GTK
        name = f'BLUE_COMBOBOX_DROPDOWNBUTTON{side}_BMP'
        if name in images:
            w, h = images[name][1].size
            put(name, Image.new('RGBA', (w, h), (0, 0, 0, 0)))
    for name in images:
        if re.fullmatch(r'BLUE_COMBOBOX_DROPDOWNBUTTON(_RIGHT|_LEFT)?_GLYPH_\d+PX_BMP', name):
            w, h = images[name][1].size
            put(name, chevron(w, h // 4, pal.fg, 4, [pal.fg] * 3 + [pal.disabled]))
    field = g.stack([g.box(ENTRY, st, 12, 12) for st in FIELD_STATES])
    for name in ('BLUE_COMBOBOX_BORDER_BMP', 'BLUE_EDIT_BORDER_NOSCROLL_BMP', 'BLUE_EDIT_BORDER_HSCROLL_BMP',
                 'BLUE_EDIT_BORDER_VSCROLL_BMP', 'BLUE_EDIT_BORDER_HVSCROLL_BMP'):
        put(name, field)
    for section in ('combobox.border', 'edit.editborder_noscroll', 'edit.editborder_hscroll',
                    'edit.editborder_vscroll', 'edit.editborder_hvscroll'):
        ini[section] = {'SizingMargins': '4, 4, 4, 4'}
    put('BLUE_GROUPBOX_BMP', _transparent_center(g.box(FRAME, 0, 24, 24)))
    ini['button.groupbox'] = {'SizingMargins': '6, 6, 6, 6', 'SizingType': 'Stretch'}
    ini.update(scrollbar.override(images, pal, put))
    return ini


def _transparent_center(img, inset=3):
    """Group boxes are drawn over the dialog: keep only the frame."""
    w, h = img.size
    img.paste((0, 0, 0, 0), (inset, inset, w - inset, h - inset))
    return img


def apply_ini(text, edits):
    """Set Key = Value in [Section] (case-insensitive) for each edit, replacing old values."""
    out, section = [], None
    lines = text.split('\r\n')
    for line in lines:
        m = re.match(r'\s*\[(.*)\]\s*$', line)
        if m:
            section = m.group(1).lower()
        else:
            key = line.partition('=')[0].strip()
            if section in edits and any(key.lower() == k.lower() for k in edits[section]):
                k = next(k for k in edits[section] if k.lower() == key.lower())
                line = f'{k} = {edits[section][k]}'
        out.append(line)
        if m and section in edits:          # keys the section did not have yet
            for k, v in edits[section].items():
                if not any(re.match(rf'\s*{re.escape(k)}\s*=', l, re.I) for l in _section_lines(lines, section)):
                    out.append(f'{k} = {v}')
    return '\r\n'.join(out)


def _section_lines(lines, section):
    inside = False
    for line in lines:
        m = re.match(r'\s*\[(.*)\]\s*$', line)
        if m:
            inside = m.group(1).lower() == section
        elif inside:
            yield line
