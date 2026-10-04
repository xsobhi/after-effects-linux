#!/usr/bin/env python3
"""Graphical installer: pick Wine, folders, an Adobe installer and options, then run
install.sh with them and show its progress.

  main.py REPO_DIR        (install.sh --gui starts it; REPO_DIR holds install.sh)
"""
import glob
import json
import os
import subprocess
import sys

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import runners  # noqa: E402
from job import Job  # noqa: E402
from pages import AdobePage, Locations, Summary, WinePage, Welcome  # noqa: E402
from widgets import label, load_css, page  # noqa: E402

HOME = os.path.expanduser('~')
APP_ID = 'io.github.xsobhi.AfterEffectsLinux'


class Installer(Gtk.Application):
    def __init__(self, repo):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.repo = repo
        self.lib = os.path.join(repo, 'lib')
        cfg = runners.config()
        self.runners = runners.find()
        self.keep_current_wine = bool(cfg.get('ADOBE_WINE_RUNNER'))   # user chose another Wine before
        self.installs = self.scan()
        self.state = {
            'runner': self.runners[0],
            'prefix': cfg.get('ADOBE_WINE_DEFAULT_PREFIX') or HOME + '/.local/share/adobe-wine/prefix',
            'runner_dir': cfg.get('ADOBE_WINE_RUNNER_DIR') or HOME + '/.local/share/adobe-wine/runner',
            'adobe_installer': '',
            'nvidia': cfg.get('ADOBE_WINE_NVIDIA', '1') != '0' and os.path.exists('/dev/nvidiactl'),
            'theme': cfg.get('ADOBE_WINE_THEME', '1') != '0',
            'menu': cfg.get('ADOBE_WINE_MENU', '1') != '0',
            'exe_handler': cfg.get('ADOBE_WINE_EXE_HANDLER', '1') != '0',
        }
        self.connect('activate', self.build)

    # --- environment ------------------------------------------------------------------
    def scan(self):
        try:
            out = subprocess.run([sys.executable, os.path.join(self.lib, 'scan.py'), '--json'],
                                 capture_output=True, text=True, timeout=60).stdout
            return json.loads(out or '[]')
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return []

    def missing_packages(self):
        out = subprocess.run([os.path.join(self.repo, 'install.sh'), '--missing-packages'],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
        return out.split()

    def install_packages(self, packages):
        """apt-get install through pkexec (the desktop's password prompt)."""
        self.show_progress('Installing system packages…')
        self.job = Job(['pkexec', 'apt-get', 'install', '-y'] + packages, self.on_progress, self.on_log,
                       self.packages_done)
        self.job.start()

    def packages_done(self, code):
        GLib.source_remove(self.pulse)
        self.go(0)
        if code:
            self.alert('The packages could not be installed', 'See the log, or install them in a terminal:\n'
                       'sudo apt install ' + ' '.join(self.pages[0].missing))

    # --- window -----------------------------------------------------------------------
    def build(self, _app):
        load_css()
        self.window = Gtk.ApplicationWindow(application=self, title='After Effects on Linux — Setup',
                                            default_width=780, default_height=600)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        root.append(self.stack)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_start=24, margin_end=24,
                      margin_top=10, margin_bottom=14)
        self.step_label = label('', 'subtle')
        self.step_label.set_hexpand(True)
        self.back = Gtk.Button(label='Back')
        self.back.connect('clicked', lambda *_: self.go(self.index - 1))
        self.next = Gtk.Button(label='Next')
        self.next.add_css_class('suggested-action')
        self.next.connect('clicked', self.on_next)
        for w in (self.step_label, self.back, self.next):
            bar.append(w)
        root.append(bar)
        self.window.set_child(root)
        self.pages = [Welcome(self), WinePage(self), Locations(self), AdobePage(self), Summary(self)]
        for i, p in enumerate(self.pages):
            self.stack.add_named(p.widget, str(i))
        self.build_progress()
        self.go(0)
        self.window.present()

    def build_progress(self):
        box = self.progress_page = page('Installing')
        self.progress_heading = box.get_first_child()
        self.progress_text = label('Starting…')
        self.progress_bar = Gtk.ProgressBar(show_text=False)
        box.append(self.progress_text)
        box.append(self.progress_bar)
        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        self.log.add_css_class('log')
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=240)
        scroll.set_child(self.log)
        self.log_scroll = scroll
        expander = Gtk.Expander(label='Details', vexpand=True)
        expander.set_child(scroll)
        box.append(expander)
        self.finish_note = label('')
        box.append(self.finish_note)
        self.stack.add_named(box, 'progress')

    def go(self, index):
        self.index = max(0, min(index, len(self.pages) - 1))
        p = self.pages[self.index]
        if hasattr(p, 'enter'):
            p.enter()
        self.stack.set_visible_child_name(str(self.index))
        self.step_label.set_text(f'Step {self.index + 1} of {len(self.pages)} · {p.title}')
        self.back.set_visible(self.index > 0)
        self.back.set_label('Back')
        self.next.set_label('Install' if self.index == len(self.pages) - 1 else 'Next')
        self.next.set_sensitive(True)
        self.next.set_visible(True)

    def on_next(self, _button):
        p = self.pages[self.index]
        if hasattr(p, 'valid') and not p.valid():
            if isinstance(p, Welcome):
                self.alert('Missing packages', 'Install the missing packages first.')
            else:
                self.alert('Check the folders', 'Folders must be full paths, e.g. /home/you/Adobe.')
            return
        if self.index == len(self.pages) - 1:
            self.run_install()
        else:
            self.go(self.index + 1)

    def alert(self, title, text):
        dialog = Gtk.AlertDialog(message=title, detail=text, modal=True)
        dialog.show(self.window)

    # --- installing -------------------------------------------------------------------
    def install_args(self):
        s = self.state
        args = [os.path.join(self.repo, 'install.sh'), '--prefix', s['prefix'], '--runner-dir', s['runner_dir']]
        args += ['--patched-wine'] if s['runner']['patched'] else ['--wine', s['runner']['root']]
        if s['adobe_installer']:
            args += ['--adobe-installer', s['adobe_installer']]
        for key, flag in (('nvidia', '--no-nvidia'), ('theme', '--no-theme'), ('menu', '--no-menu'),
                          ('exe_handler', '--no-exe-handler')):
            if not s[key]:
                args.append(flag)
        return args

    def show_progress(self, text):
        self.stack.set_visible_child_name('progress')
        self.progress_heading.set_text('Installing')
        self.progress_text.set_text(text)
        self.progress_bar.set_fraction(0)
        self.log.get_buffer().set_text('')
        self.finish_note.set_text('')
        self.back.set_visible(False)
        self.next.set_visible(False)
        self.step_label.set_text('')
        self.pulse = GLib.timeout_add(150, self.pulse_bar)

    def run_install(self):
        self.show_progress('Starting…')
        self.job = Job(self.install_args(), self.on_progress, self.on_log, self.install_done)
        self.job.start()

    def pulse_bar(self):
        if self.progress_bar.get_fraction() == 0:
            self.progress_bar.pulse()
        return True

    def on_progress(self, fraction, text):
        if fraction is not None:
            self.progress_bar.set_fraction(fraction)
        self.progress_text.set_text(text)

    def on_log(self, line):
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), line + '\n')
        adj = self.log_scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()) and False)

    def install_done(self, code):
        GLib.source_remove(self.pulse)
        if code:
            self.progress_text.set_markup('<b>Setup stopped with an error.</b> Open “Details” for the log.')
            self.back.set_visible(True)
            self.back.set_label('Back to settings')
            return
        self.progress_bar.set_fraction(1)
        self.progress_heading.set_text('All set')
        self.progress_text.set_markup('<b>After Effects on Linux is installed.</b>')
        names = []
        for path in sorted(glob.glob(os.path.join(HOME, '.local/share/applications/adobe-wine-*.desktop'))):
            with open(path) as f:
                entry = f.read()
            if 'NoDisplay=true' not in entry:
                names += [line[5:] for line in entry.splitlines() if line.startswith('Name=')][:1]
        text = ('Start ' + ', '.join(names) + ' from the applications menu.\n' if names else
                'No Adobe app is installed yet: double-click your Adobe Set-up.exe to install it.\n')
        text += ('Double-click any Windows installer (Adobe apps, plugins, presets) to install it into '
                 'this Wine. Run “After Effects Linux Setup” from the menu to change these settings.')
        self.finish_note.set_text(text)
        self.next.set_label('Close')
        self.next.set_visible(True)
        self.next.disconnect_by_func(self.on_next)
        self.next.connect('clicked', lambda *_: self.quit())


if __name__ == '__main__':
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    sys.exit(Installer(os.path.abspath(repo)).run([sys.argv[0]]))
