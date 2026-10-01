#!/usr/bin/env python3
"""Show the desktop's own file chooser (xdg-desktop-portal) for a Wine app.

Started by filedialog.dll inside Wine:  filechooser.py REQUEST RESULT
REQUEST lines (UTF-8, key=value, "\\n" escaped):
  mode=open|save|folder   multiple=0|1   title=   accept=   parent=x11:<hex xid>
  folder=/unix/dir   name=file.ext   filter_index=N
  filter=<name>\t<glob>;<glob>                       (repeated, in order)
  choice=<id>\t<label>\t<default>\t<id>:<label>|...  (no options = checkbox)
RESULT is written atomically: response=0|1|2, path=... (repeated), filter_index=N,
choice=<id>\t<value> (repeated), error=...
"""
import os
import sys

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib  # noqa: E402

PORTAL = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'


def unescape(v):
    return v.replace('\\n', '\n').replace('\\\\', '\\')


def escape(v):
    return v.replace('\\', '\\\\').replace('\n', '\\n')


def read_request(path):
    req = {'filter': [], 'choice': []}
    with open(path, encoding='utf-8') as f:
        for line in f.read().splitlines():
            key, _, value = line.partition('=')
            value = unescape(value)
            if key in ('filter', 'choice'):
                req[key].append(value.split('\t'))
            else:
                req[key] = value
    return req


def any_case(glob):
    """Windows matches extensions case-insensitively; GTK globs do not."""
    if glob in ('*.*', '*'):
        return '*'
    return ''.join(f'[{c.lower()}{c.upper()}]' if c.isalpha() else c for c in glob)


def build_options(req, token):
    opts = {'handle_token': GLib.Variant('s', token), 'modal': GLib.Variant('b', True)}
    if req.get('accept'):
        opts['accept_label'] = GLib.Variant('s', req['accept'])
    if req.get('mode') == 'folder':
        opts['directory'] = GLib.Variant('b', True)
    if req.get('multiple') == '1':
        opts['multiple'] = GLib.Variant('b', True)
    filters = [(name, [(0, any_case(g)) for g in globs.split(';') if g])
               for name, globs in (f + [''] if len(f) == 1 else f for f in req['filter'])]
    filters = [f for f in filters if f[1]]
    if filters:
        opts['filters'] = GLib.Variant('a(sa(us))', filters)
        index = int(req.get('filter_index') or 0)
        if 0 <= index < len(filters):
            opts['current_filter'] = GLib.Variant('(sa(us))', filters[index])
    choices = []
    for c in req['choice']:
        cid, label, default = (c + ['', '', ''])[:3]
        options = [tuple(o.split(':', 1)) for o in (c[3].split('|') if len(c) > 3 and c[3] else [])]
        options = [o for o in options if len(o) == 2]
        choices.append((cid, label, options, default or ('' if options else 'false')))
    if choices:
        opts['choices'] = GLib.Variant('a(ssa(ss)s)', choices)
    folder = req.get('folder')
    if folder and os.path.isdir(folder):
        opts['current_folder'] = GLib.Variant('ay', os.fsencode(folder) + b'\0')
    if req.get('mode') == 'save' and req.get('name'):
        opts['current_name'] = GLib.Variant('s', req['name'])
    return opts, filters


def run(req):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    token = f'adobewine{os.getpid()}'
    sender = bus.get_unique_name()[1:].replace('.', '_')
    handle = f'{PATH}/request/{sender}/{token}'
    loop, answer = GLib.MainLoop(), {}

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        answer['code'], answer['results'] = params.unpack()
        loop.quit()

    bus.signal_subscribe(PORTAL, 'org.freedesktop.portal.Request', 'Response', handle,
                         None, Gio.DBusSignalFlags.NO_MATCH_RULE, on_response)
    opts, filters = build_options(req, token)
    method = 'SaveFile' if req.get('mode') == 'save' else 'OpenFile'
    bus.call_sync(PORTAL, PATH, 'org.freedesktop.portal.FileChooser', method,
                  GLib.Variant('(ssa{sv})', (req.get('parent', ''), req.get('title', ''), opts)),
                  None, Gio.DBusCallFlags.NONE, 120000, None)
    loop.run()
    return answer['code'], answer['results'], filters


def main(request_path, result_path):
    out = []
    started = result_path + '.started'
    open(started, 'w').close()          # tells filedialog.dll the helper is alive
    try:
        code, results, filters = run(read_request(request_path))
        out.append(f'response={min(code, 1)}')
        for uri in results.get('uris', []):
            out.append('path=' + escape(Gio.File.new_for_uri(uri).get_path() or ''))
        current = results.get('current_filter')
        if current and filters:
            names = [f[0] for f in filters]
            if current[0] in names:
                out.append(f'filter_index={names.index(current[0])}')
        for cid, value in results.get('choices', []):
            out.append(f'choice={escape(cid)}\t{escape(value)}')
    except Exception as exc:  # report, so the DLL can fall back to Wine's dialog
        out = ['response=2', 'error=' + escape(str(exc))]
    tmp = result_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    os.replace(tmp, result_path)
    os.unlink(started)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
