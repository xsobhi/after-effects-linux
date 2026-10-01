#!/usr/bin/env python3
"""Window-manager touches that Wine leaves out, for one app's windows.

  * Dark title bars when the desktop theme is dark: Muffin/Mutter read
    _GTK_THEME_VARIANT, which GTK dark-theme apps set and Wine does not.
  * No compositor shadow on borderless popups (e.g. the text panel of Adobe's splash
    screen): Windows draws none there, Muffin shadows every opaque override-redirect
    window. An opacity of 254/255 opts out (Muffin skips non-opaque windows).
Menus, tooltips and combo lists keep their shadows.

Usage: wm_helper.py WM_CLASS [PARENT_PID]   (exits with the parent process)
"""
import os
import select
import subprocess
import sys

from Xlib import X, Xatom, display, error

OPACITY_NO_SHADOW = 0xfeffffff
SHADOWED_TYPES = ('MENU', 'POPUP_MENU', 'DROPDOWN_MENU', 'TOOLTIP', 'COMBO', 'NOTIFICATION', 'DND')


def desktop_is_dark():
    for schema, key in (('org.x.apps.portal', 'color-scheme'),
                        ('org.gnome.desktop.interface', 'color-scheme'),
                        ('org.cinnamon.desktop.interface', 'gtk-theme'),
                        ('org.gnome.desktop.interface', 'gtk-theme')):
        try:
            value = subprocess.run(['gsettings', 'get', schema, key], capture_output=True,
                                   text=True, timeout=3).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        if 'dark' in value.lower():
            return True
    return False


class Helper:
    def __init__(self, wm_class, parent):
        self.d = display.Display()
        self.root = self.d.screen().root
        self.wm_class, self.parent, self.dark = wm_class, parent, desktop_is_dark()
        self.atom = self.d.intern_atom
        self.done = set()

    def matches(self, win):
        try:
            cls = win.get_wm_class()
        except error.XError:
            return False
        return bool(cls) and self.wm_class in cls

    def window_types(self, win):
        try:
            prop = win.get_full_property(self.atom('_NET_WM_WINDOW_TYPE'), Xatom.ATOM)
        except error.XError:
            return []
        return [self.d.get_atom_name(a).replace('_NET_WM_WINDOW_TYPE_', '') for a in (prop.value if prop else [])]

    def handle(self, win, depth=0):
        """Check a newly mapped window; managed windows sit inside the WM's frame."""
        if win.id in self.done:
            return
        if not self.matches(win):
            if depth < 2:
                try:
                    kids = win.query_tree().children
                except error.XError:
                    return
                for kid in kids:
                    self.handle(kid, depth + 1)
            return
        try:
            attrs, geo = win.get_attributes(), win.get_geometry()
        except error.XError:
            return
        if attrs.map_state != X.IsViewable:
            return
        self.done.add(win.id)
        if not attrs.override_redirect:
            if self.dark:
                win.change_property(self.atom('_GTK_THEME_VARIANT'), self.atom('UTF8_STRING'), 8, b'dark')
        elif geo.depth != 32 and not set(self.window_types(win)) & set(SHADOWED_TYPES):
            win.change_property(self.atom('_NET_WM_WINDOW_OPACITY'), Xatom.CARDINAL, 32, [OPACITY_NO_SHADOW])
        self.d.flush()

    def scan(self):
        for win in self.root.query_tree().children:
            self.handle(win)

    def run(self):
        self.root.change_attributes(event_mask=X.SubstructureNotifyMask)
        self.scan()
        while True:
            if self.parent and not os.path.exists(f'/proc/{self.parent}'):
                return
            # Wait for X events without busy-looping; wake every 2 s to check the parent.
            if not self.d.pending_events():
                select.select([self.d.fileno()], [], [], 2.0)
            while self.d.pending_events():
                event = self.d.next_event()
                if event.type == X.MapNotify:
                    self.handle(event.window)
                elif event.type == X.DestroyNotify:
                    self.done.discard(event.window.id)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        Helper(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0).run()
    except (error.DisplayError, ConnectionError, KeyboardInterrupt):
        pass
