"""Render GTK 3 widget parts with the desktop theme, as RGBA images for a Windows theme.

Each function returns a PIL image. Parts are drawn through GtkStyleContext with CSS-node
paths ("checkbutton check", "button", ...), at 2x scale so themes with HiDPI assets use
them, then scaled down, which also gives the edges proper anti-aliasing.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402
import cairo  # noqa: E402
from PIL import Image  # noqa: E402

S = Gtk.StateFlags
SCALE = 2                   # matches the @2 assets GTK themes ship
_settings_done = False


def use_theme(name, dark):
    """Render with NAME regardless of the session's XSETTINGS (the hidden test display has none)."""
    global _settings_done
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-theme-name', name)
    settings.set_property('gtk-application-prefer-dark-theme', bool(dark))
    _settings_done = True


def _context(nodes, state=0):
    """nodes: [('checkbutton', []), ('check', [])] - object names with style classes."""
    path = Gtk.WidgetPath()
    path.append_type(Gtk.Window)
    path.iter_set_object_name(-1, 'window')
    path.iter_add_class(-1, 'background')
    parent = None
    for name, classes in nodes:
        path.append_type(Gtk.Widget)
        path.iter_set_object_name(-1, name)
        for c in classes:
            path.iter_add_class(-1, c)
        ctx = Gtk.StyleContext()
        ctx.set_path(path)
        if parent:
            ctx.set_parent(parent)
        ctx.set_state(Gtk.StateFlags(state))
        ctx.set_scale(2)
        parent = ctx
    return parent


def _surface(w, h):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * SCALE, h * SCALE)
    cr = cairo.Context(surf)
    cr.scale(SCALE, SCALE)
    return surf, cr


def _image(surf, w, h):
    """Un-premultiply cairo's BGRA and downsample to w x h."""
    img = Image.frombuffer('RGBA', (surf.get_width(), surf.get_height()), bytes(surf.get_data()),
                           'raw', 'BGRa', surf.get_stride(), 1)
    return img.resize((w, h), Image.LANCZOS)


def box(nodes, state, w, h, inset=0):
    """Background + frame of a box-like node (button, entry, trough, tab...)."""
    surf, cr = _surface(w, h)
    ctx = _context(nodes, state)
    Gtk.render_background(ctx, cr, inset, inset, w - 2 * inset, h - 2 * inset)
    Gtk.render_frame(ctx, cr, inset, inset, w - 2 * inset, h - 2 * inset)
    return _image(surf, w, h)


def indicator(kind, state, size):
    """Check box or radio indicator, drawn to fill size x size."""
    surf, cr = _surface(size, size)
    node = ('checkbutton', 'check') if kind == 'check' else ('radiobutton', 'radio')
    ctx = _context([(node[0], []), (node[1], [])], state)
    Gtk.render_background(ctx, cr, 0, 0, size, size)
    Gtk.render_frame(ctx, cr, 0, 0, size, size)
    (Gtk.render_check if kind == 'check' else Gtk.render_option)(ctx, cr, 0, 0, size, size)
    return _image(surf, size, size)


def color(nodes, prop='color', state=0):
    """A CSS colour of a node as (r, g, b, a) 0-255."""
    ctx = _context(nodes, state)
    state = Gtk.StateFlags(state)
    rgba = ctx.get_color(state) if prop == 'color' else ctx.get_property(prop, state)
    return tuple(round(c * 255) for c in (rgba.red, rgba.green, rgba.blue, rgba.alpha))


def arrow(nodes, state, w, h, glyph=8, angle=3.14159):
    """A dropdown/scroll arrow centred in w x h (angle pi = pointing down)."""
    surf, cr = _surface(w, h)
    ctx = _context(nodes, state)
    Gtk.render_arrow(ctx, cr, angle, (w - glyph) / 2, (h - glyph) / 2, glyph)
    return _image(surf, w, h)


def stack(images):
    """Stack state images vertically (the msstyles ImageLayout = Vertical order)."""
    w, h = images[0].size
    out = Image.new('RGBA', (w, h * len(images)))
    for i, img in enumerate(images):
        out.paste(img, (0, i * h))
    return out
