"""The installer's pages. Each page has .widget, .title and optionally .enter()/.valid()."""
import os

from gi.repository import Gtk

from widgets import PathPicker, badge, free_space, label, note, page

HOME = os.path.expanduser('~')


class Welcome:
    title = 'Welcome'

    def __init__(self, app):
        self.app = app
        box = self.widget = page('After Effects on Linux',
                                 'This sets up Wine to run your own Adobe After Effects and Media '
                                 'Encoder (and their plugins), made to feel at home on Linux.')
        for text in ('Downloads a Wine build with the fixes Adobe apps need (or uses a Wine you pick)',
                     'Creates the Windows environment: fonts, runtimes, GPU support (NVIDIA CUDA)',
                     'Native file dialogs, your desktop theme and fonts, menu entries',
                     'Optionally runs your Adobe installer right after'):
            box.append(label('•  ' + text))
        box.append(label('No Adobe software is included: you need your own installer and an Adobe '
                         'account.', 'subtle'))
        self.found = note('')
        box.append(self.found)
        self.deps = note('', warn=True)
        self.deps_button = Gtk.Button(label='Install missing packages…', halign=Gtk.Align.START)
        self.deps_button.connect('clicked', lambda *_: app.install_packages(self.missing))
        box.append(self.deps)
        box.append(self.deps_button)
        self.missing = []

    def enter(self):
        installs = self.app.installs
        if installs:
            lines = [f"{a['folder']} ({a['version']}) in {a['prefix'].replace(HOME, '~')}" for a in installs]
            self.found.text.set_text('Already installed: ' + '; '.join(lines) + '. Setup keeps them and '
                                     'sets them up again.')
        self.found.set_visible(bool(installs))
        self.missing = self.app.missing_packages()
        self.deps.text.set_text('Some system packages are missing: ' + ' '.join(self.missing))
        self.deps.set_visible(bool(self.missing))
        self.deps_button.set_visible(bool(self.missing))

    def valid(self):
        return not self.missing


class WinePage:
    title = 'Wine'

    def __init__(self, app):
        self.app = app
        box = self.widget = page('Choose Wine',
                                 'Wine runs the Windows programs. These are the Wine versions found '
                                 'on this computer.')
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class('boxed-list')
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.list)
        box.append(scroll)
        self.warning = note('This Wine does not have the fixes After Effects needs (start-up crash at '
                            '"Initializing MediaCore", sign-in page, text engine, installers, display). '
                            'Use it only if you know it works for you.', warn=True)
        box.append(self.warning)
        if not any(r['default'] for r in app.runners):
            box.append(label('This computer has no system Wine installed (no default Wine); the '
                             'recommended one is used for After Effects either way.', 'subtle'))
        group = None
        for r in app.runners:
            check = Gtk.CheckButton(group=group)
            group = group or check
            check.set_valign(Gtk.Align.CENTER)
            check.connect('toggled', self._toggled, r)
            r['check'] = check
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class('wine-row')
            row.append(check)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            title.append(label(r['name'], wrap=False, markup=False))
            if r['patched']:
                title.append(badge('Recommended · includes the Adobe fixes', 'good'))
                title.append(badge('Installed' if r['installed'] else 'Downloaded during setup', 'info'))
            if r['default']:
                title.append(badge("This computer's default Wine", 'info'))
            if r.get('current') and not r['patched']:
                title.append(badge('In use now', 'info'))
            text.append(title)
            where = 'will be downloaded' if not r['installed'] else r['root'].replace(HOME, '~')
            text.append(label(f"{r['source']} · {r['version'] or 'unknown version'} · {where}", 'subtle'))
            row.append(text)
            gesture = Gtk.GestureClick()
            gesture.connect('released', lambda *_a, c=check: c.set_active(True))
            row.add_controller(gesture)
            self.list.append(row)
        chosen = next((r for r in app.runners if r.get('current')), app.runners[0])
        if not chosen['patched'] and not app.keep_current_wine:
            chosen = app.runners[0]
        chosen['check'].set_active(True)
        self._toggled(chosen['check'], chosen)

    def _toggled(self, check, runner):
        if check.get_active():
            self.app.state['runner'] = runner
            self.warning.set_visible(not runner['patched'])


class Locations:
    title = 'Locations'

    def __init__(self, app):
        self.app = app
        s = app.state
        box = self.widget = page('Where to put things')
        box.append(label('<b>Windows environment (Wine prefix)</b>', markup=True))
        box.append(label('Your Adobe apps, plugins, presets and their settings are installed here. '
                         'Allow about 15 GB for After Effects.', 'subtle'))
        self.prefix = PathPicker(app.window, s['prefix'], on_change=self._changed)
        box.append(self.prefix)
        self.prefix_info = label('', 'subtle')
        box.append(self.prefix_info)
        self.runner_title = label('<b>Wine download</b>', markup=True)
        box.append(self.runner_title)
        self.runner_text = label('The Wine build with the Adobe fixes (about 450 MB to download, 1.3 GB '
                                 'unpacked).', 'subtle')
        box.append(self.runner_text)
        self.runner = PathPicker(app.window, s['runner_dir'], on_change=self._changed)
        box.append(self.runner)
        self.runner_info = label('', 'subtle')
        box.append(self.runner_info)

    def enter(self):
        patched = self.app.state['runner']['patched']
        for w in (self.runner_title, self.runner_text, self.runner, self.runner_info):
            w.set_visible(patched)
        self._changed()

    def _changed(self, *_):
        s = self.app.state
        s['prefix'], s['runner_dir'] = self.prefix.get(), self.runner.get()
        found = [a for a in self.app.installs if os.path.realpath(a['prefix']) == os.path.realpath(s['prefix'])]
        info = free_space(s['prefix'])
        if found:
            info += ' · contains ' + ', '.join(a['folder'] for a in found) + ' (kept, set up again)'
        elif os.path.isfile(os.path.join(s['prefix'], 'system.reg')):
            info += ' · existing Wine prefix (kept)'
        self.prefix_info.set_text(info)
        self.runner_info.set_text(free_space(s['runner_dir']))

    def valid(self):
        s = self.app.state
        return bool(s['prefix'] and os.path.isabs(s['prefix']) and s['runner_dir'] and os.path.isabs(s['runner_dir']))


class AdobePage:
    title = 'Adobe & options'

    def __init__(self, app):
        self.app = app
        s = app.state
        box = self.widget = page('Adobe installer and options')
        box.append(label('<b>Adobe installer (optional)</b>', markup=True))
        box.append(label("Pick your Adobe Set-up.exe to install After Effects or Media Encoder right "
                         "after setup. Leave it empty if they are installed already or you'll do it "
                         "later.", 'subtle'))
        self.setup = PathPicker(app.window, s['adobe_installer'], folder=False,
                                patterns=['*.exe', '*.EXE'], on_change=lambda v: s.update(adobe_installer=v))
        box.append(self.setup)
        box.append(label('<b>Options</b>', markup=True))
        self.checks = {}
        options = [('menu', 'Add the Adobe apps to the applications menu and open .aep projects with After Effects'),
                   ('exe_handler', 'Open Windows installers (.exe, .msi) with this Wine when double-clicked'),
                   ('theme', 'Match the desktop theme (colours, fonts, controls)')]
        if os.path.exists('/dev/nvidiactl'):
            options.append(('nvidia', 'Use the NVIDIA GPU (CUDA, OpenGL) on this hybrid-graphics computer'))
        for key, text in options:
            check = Gtk.CheckButton(label=text, active=s[key])
            check.connect('toggled', lambda c, k=key: s.update({k: c.get_active()}))
            box.append(check)
        box.append(note('After setup you can double-click any Windows installer — another Adobe app, '
                        'plugins such as Red Giant, Boris FX, Video Copilot or Maxon, or presets '
                        'installers — and it installs into this Wine, where After Effects finds it.'))


class Summary:
    title = 'Install'

    def __init__(self, app):
        self.app = app
        self.widget = page('Ready to install')
        self.text = label('')
        self.widget.append(self.text)
        self.widget.append(label('Apps running in this Wine are closed first. The first run downloads '
                                 'Wine, fonts and runtimes and takes about 10 minutes.', 'subtle'))

    def enter(self):
        s = self.app.state
        r = s['runner']
        lines = [f"<b>Wine:</b> {r['name']}" + ('' if r['patched'] else ' — <i>without the Adobe fixes</i>'),
                 f"<b>Prefix:</b> {s['prefix']}"]
        if r['patched']:
            lines.append(f"<b>Wine download:</b> {s['runner_dir']}")
        if s['adobe_installer']:
            lines.append(f"<b>Then run:</b> {s['adobe_installer']}")
        opts = [n for k, n in (('menu', 'menu entries'), ('exe_handler', 'open .exe with this Wine'),
                               ('theme', 'desktop theme'), ('nvidia', 'NVIDIA GPU')) if s.get(k)]
        lines.append('<b>Options:</b> ' + (', '.join(opts) or 'none'))
        self.text.set_markup('\n'.join(GLib_escape(line) for line in lines))


def GLib_escape(line):
    """Escape & and < in paths but keep our own <b>/<i> tags."""
    return (line.replace('&', '&amp;').replace('<', '&lt;').replace('&lt;b>', '<b>')
            .replace('&lt;/b>', '</b>').replace('&lt;i>', '<i>').replace('&lt;/i>', '</i>'))
