"""Map Wine's Light theme (bitmaps and ini colours) onto the desktop palette, and convert
between PIL images and the DIBs stored in RT_BITMAP resources."""
import colorsys
import struct

from PIL import Image

MAGENTA = (255, 0, 255)      # msstyles' default transparent colour: keep it as is


def dib_to_image(dib):
    size, w, h, _, bpp = struct.unpack_from('<IiiHH', dib, 0)
    colors = struct.unpack_from('<I', dib, 32)[0] if bpp <= 8 else 0
    bits = dib[size + 4 * colors:]
    mode, raw = ('RGBA', 'BGRA') if bpp == 32 else ('RGB', 'BGR')
    stride = (w * bpp // 8 + 3) & ~3
    img = Image.frombuffer(mode, (w, abs(h)), bits, 'raw', raw, stride, -1 if h > 0 else 1)
    return img.copy(), bpp


def image_to_dib(img, bpp):
    img = img.convert('RGBA' if bpp == 32 else 'RGB')
    w, h = img.size
    stride = (w * bpp // 8 + 3) & ~3
    raw = img.tobytes('raw', 'BGRA' if bpp == 32 else 'BGR', stride, -1)
    header = struct.pack('<IiiHHIIiiII', 40, w, h, 1, bpp, 0, len(raw), 2835, 2835, 0, 0)
    return header + raw


def _mix(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class Palette:
    """Desktop colours: bg, base (fields), fg, disabled, border, hover, accent."""

    def __init__(self, bg, base, fg, disabled, border, accent):
        self.bg, self.base, self.fg, self.disabled = bg, base, fg, disabled
        self.border, self.accent = border, accent
        dark = sum(bg) / 3 < 128
        self.hover = _mix(bg, (255, 255, 255) if dark else (0, 0, 0), 0.08)
        # Dark themes outline controls with a lighter line than their (darker) border colour.
        self.line = _mix(bg, fg, 0.28) if dark else border

    def surface(self, rgb):
        """A Light-theme surface/border/glyph colour -> the matching desktop colour."""
        if rgb == MAGENTA:
            return rgb
        h, light, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        lum = light * 255
        if s > 0.35 and 0.15 < light < 0.9:              # accent-coloured (blue) pixels
            return _mix(self.accent, self.surface_grey(lum), 1 - min(1.0, s))
        return self.surface_grey(lum)

    def surface_grey(self, lum):
        if lum >= 225:                                    # backgrounds and hover tints
            return _mix(self.base, self.hover, (255 - lum) / 30)
        if lum >= 140:                                    # borders
            return _mix(self.line, self.hover, (lum - 140) / 85)
        return _mix(self.fg, self.line, lum / 140)       # glyphs, arrows, check marks

    def text(self, rgb):
        """A Light-theme text colour -> fg, or the disabled colour for greyed text."""
        lum = sum(rgb) / 3
        if lum >= 200 or lum < 60:                        # black text, or white on accent
            return self.fg
        return _mix(self.fg, self.disabled, lum / 166)


def recolor_image(img, pal):
    """Recolour every pixel; alpha (32-bit) and the magenta colour key are kept."""
    has_alpha = img.mode == 'RGBA'
    src = img.convert('RGBA')
    cache, out = {}, []
    for r, g, b, a in src.getdata():
        key = (r, g, b)
        if key not in cache:
            cache[key] = pal.surface(key)
        out.append(cache[key] + (a,))
    res = Image.new('RGBA', src.size)
    res.putdata(out)
    return res if has_alpha else res.convert('RGB')


TEXT_KEYS = ('textcolor', 'textshadowcolor', 'glowcolor', 'glyphtextcolor', 'textcolorhint')


def recolor_ini(text, pal):
    """Rewrite every 'Key = R G B' line; drop the theme's own fonts (keep the desktop's)."""
    out = []
    for line in text.split('\r\n'):
        key, sep, value = line.partition('=')
        k = key.strip().lower()
        parts = value.split()
        if sep and k.endswith('font') or k in ('captionbarheight', 'smcaptionbarheight', 'smcaptionbarwidth'):
            continue
        if sep and len(parts) == 3 and all(p.isdigit() for p in parts):
            rgb = tuple(int(p) for p in parts)
            new = pal.text(rgb) if k in TEXT_KEYS or k.endswith('text') else pal.surface(rgb)
            line = f'{key}= {new[0]} {new[1]} {new[2]}'
        out.append(line)
    return '\r\n'.join(out)
