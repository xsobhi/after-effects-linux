"""Scroll bars in the GTK style: flat trough, rounded thumb, no boxed arrow buttons."""
import cairo
from PIL import Image

import gtk_render as g
from recolor import _mix

S = g.S
SLIDER = [('scrollbar', ['vertical']), ('contents', []), ('trough', []), ('slider', [])]
TROUGH = [('scrollbar', ['vertical']), ('contents', []), ('trough', [])]


def _sample(nodes, state, under):
    """The node's background colour composited over UNDER (sampled from a render)."""
    img = g.box(nodes, state, 12, 40)
    r, gr, b, a = img.getpixel((6, 20))
    t = a / 255
    return tuple(round(c * t + u * (1 - t)) for c, u in zip((r, gr, b), under))


def _thumb(w, h, horizontal, rgb, inset):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * 4, h * 4)
    cr = cairo.Context(surf)
    cr.scale(4, 4)
    x, y, tw, th = (1, inset, w - 2, h - 2 * inset) if horizontal else (inset, 1, w - 2 * inset, h - 2)
    r = min(tw, th) / 2
    cr.new_sub_path()
    cr.arc(x + tw - r, y + r, r, -1.5708, 0)
    cr.arc(x + tw - r, y + th - r, r, 0, 1.5708)
    cr.arc(x + r, y + th - r, r, 1.5708, 3.14159)
    cr.arc(x + r, y + r, r, 3.14159, 4.71239)
    cr.close_path()
    cr.set_source_rgb(*(c / 255 for c in rgb))
    cr.fill()
    return g._image(surf, w, h)


def override(images, pal, put):
    """Replace the scroll bar bitmaps; returns ini edits."""
    trough = _sample(TROUGH, 0, pal.bg)
    colors = [_sample(SLIDER, st, trough) for st in (0, S.PRELIGHT, S.ACTIVE | S.PRELIGHT)]
    colors = colors + [trough, colors[0]]            # normal, hot, pressed, disabled, hover
    hover = _mix(trough, pal.fg, 0.08) + (255,)
    if 'BLUE_SCROLLBAR_ARROWS_BMP' in images:
        w, h = images['BLUE_SCROLLBAR_ARROWS_BMP'][1].size
        cells = []
        for i in range(20):                          # up/down/left/right x normal/hot/pressed/disabled, hover
            state = i % 4 if i < 16 else 0
            cells.append(Image.new('RGBA', (w, h // 20), hover if state in (1, 2) else trough + (255,)))
        put('BLUE_SCROLLBAR_ARROWS_BMP', g.stack(cells))
    put('BLUE_SCROLLBAR_THUMB_VERTICAL_BMP', g.stack([_thumb(17, 24, False, c, 5) for c in colors]))
    put('BLUE_SCROLLBAR_THUMB_HORIZONTAL_BMP', g.stack([_thumb(24, 17, True, c, 5) for c in colors]))
    for name in images:
        if name.startswith(('BLUE_SCROLLBAR_LOWER_TRACK', 'BLUE_SCROLLBAR_UPPER_TRACK')):
            w, h = images[name][1].size
            put(name, Image.new('RGBA', (w, h), trough + (255,)))
        elif name.startswith('BLUE_SCROLLBAR_GRIPPER'):
            put(name, Image.new('RGBA', images[name][1].size, (0, 0, 0, 0)))
    return {'scrollbar.thumbbtnvert': {'SizingMargins': '8, 8, 8, 8'},
            'scrollbar.thumbbtnhorz': {'SizingMargins': '8, 8, 8, 8'},
            'scrollbar.sizeboxbkgnd': {'FillColor': ' '.join(map(str, trough))}}
