"""Small GTK 4 building blocks shared by the installer pages."""
import os

from gi.repository import Gio, GLib, Gtk, Pango

CSS = b"""
.page { padding: 28px 36px; }
.heading { font-size: 20pt; font-weight: 700; }
.subtle { opacity: 0.72; }
.badge { border-radius: 99px; padding: 1px 9px; font-size: 9pt; font-weight: 600; }
.badge.good { background: alpha(#2ec27e, 0.22); color: #26a269; }
.badge.info { background: alpha(#3584e4, 0.20); color: #3584e4; }
.badge.warn { background: alpha(#e5a50a, 0.24); color: #c88800; }
.note { border-radius: 8px; padding: 10px 14px; background: alpha(currentColor, 0.06); }
.note.warn { background: alpha(#e5a50a, 0.16); }
.wine-row { padding: 8px 6px; }
.log { font-family: monospace; font-size: 9pt; }
"""


def load_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gtk.Widget.get_display(Gtk.Label()), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def label(text, *classes, wrap=True, markup=False, xalign=0.0):
    w = Gtk.Label(xalign=xalign)
    if markup:
        w.set_markup(text)
    else:
        w.set_text(text)
    if wrap:
        w.set_wrap(True)
        w.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    for c in classes:
        w.add_css_class(c)
    return w


def badge(text, kind):
    w = label(text, 'badge', kind, wrap=False)
    w.set_valign(Gtk.Align.CENTER)
    return w


def note(text, warn=False, markup=False):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.add_css_class('note')
    if warn:
        box.add_css_class('warn')
    icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic' if warn else 'dialog-information-symbolic')
    icon.set_valign(Gtk.Align.START)
    box.append(icon)
    text_label = label(text, markup=markup)
    text_label.set_hexpand(True)
    box.append(text_label)
    box.text = text_label
    return box


def page(title, intro=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.add_css_class('page')
    box.append(label(title, 'heading'))
    if intro:
        box.append(label(intro, 'subtle'))
    return box


def free_space(path):
    """'123 GB free' for the filesystem the (maybe not yet existing) path would be on."""
    p = os.path.abspath(os.path.expanduser(path))
    while not os.path.exists(p) and p != '/':
        p = os.path.dirname(p)
    try:
        st = os.statvfs(p)
    except OSError:
        return ''
    return f'{st.f_bavail * st.f_frsize / 1e9:.0f} GB free'


class PathPicker(Gtk.Box):
    """Entry + "Choose…" button; folder=True picks a folder, else a file (patterns)."""

    def __init__(self, window, value, folder=True, patterns=None, on_change=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.window, self.folder, self.patterns = window, folder, patterns or []
        self.entry = Gtk.Entry(text=value, hexpand=True)
        self.append(self.entry)
        button = Gtk.Button(label='Choose…')
        button.connect('clicked', self._choose)
        self.append(button)
        if on_change:
            self.entry.connect('changed', lambda *_: on_change(self.get()))

    def get(self):
        return os.path.expanduser(self.entry.get_text().strip())

    def _choose(self, _button):
        dialog = Gtk.FileDialog(modal=True)
        current = self.get()
        start = current if self.folder else os.path.dirname(current)
        if start and os.path.isdir(start):
            dialog.set_initial_folder(Gio.File.new_for_path(start))
        if self.patterns:
            filt = Gtk.FileFilter(name=' '.join(self.patterns))
            for p in self.patterns:
                filt.add_pattern(p)
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(filt)
            dialog.set_filters(store)
        if self.folder:
            dialog.select_folder(self.window, None, self._done, dialog.select_folder_finish)
        else:
            dialog.open(self.window, None, self._done, dialog.open_finish)

    def _done(self, dialog, result, finish):
        try:
            f = finish(result)
        except GLib.Error:                  # cancelled
            return
        if f and f.get_path():
            self.entry.set_text(f.get_path())
