"""Run install.sh (or another command) in the background and report its progress.

install.sh prints "==> step" lines; curl's download meter rewrites one line with \\r. Both are
turned into (fraction, text) updates; every output line also goes to the log callback.
"""
import os
import re
import subprocess
import threading

from gi.repository import GLib

ANSI = re.compile(r'\x1b\[[0-9;]*m')
CURL = re.compile(r'^\s*(\d{1,3})\s+\S+\s+\d{1,3}\s')
# "==>" step text -> overall progress when it starts
STEPS = [
    ('Wine runner', 0.02, 'Getting Wine (about 450 MB the first time)…'),
    ('Wine:', 0.02, 'Using the chosen Wine…'),
    ('Unpacking the runner', 0.22, 'Unpacking Wine…'),
    ('Applying the Adobe fixes', 0.27, 'Applying the Adobe fixes to Wine…'),
    ('Tools', 0.30, 'Installing the tools…'),
    ('Preparing Wine prefix', 0.33, 'Creating the Windows environment…'),
    ('Microsoft core fonts', 0.42, 'Installing Microsoft fonts and MSXML…'),
    ('Visual C++', 0.55, 'Installing the Visual C++ runtimes…'),
    ('GDI+', 0.60, 'Installing GDI+…'),
    ('DXVK', 0.66, 'Installing GPU support (DXVK, CUDA)…'),
    ('Matching the desktop theme', 0.75, 'Matching your desktop theme…'),
    ('Done.', 0.88, 'Creating menu entries…'),
    ('Running the Adobe installer', 0.90, 'Running the Adobe installer: sign in when it asks…'),
    ('Installed.', 1.0, 'Finished'),
]


class Job:
    """Runs argv; on_progress(fraction or None, text), on_log(line), on_done(exit code)."""

    def __init__(self, argv, on_progress, on_log, on_done, env=None):
        self.argv, self.on_progress, self.on_log, self.on_done = argv, on_progress, on_log, on_done
        self.env = dict(os.environ, **(env or {}))
        self.proc = None
        self.fraction = 0.0
        self.downloading = False

    def start(self):
        self.proc = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, env=self.env)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b''
        while chunk := self.proc.stdout.read1(4096):
            buf += chunk
            *parts, buf = re.split(rb'[\r\n]', buf)
            for part in parts:
                self._line(ANSI.sub('', part.decode('utf-8', 'replace')).rstrip())
        if buf:
            self._line(ANSI.sub('', buf.decode('utf-8', 'replace')).rstrip())
        code = self.proc.wait()
        GLib.idle_add(self.on_done, code)

    def _line(self, line):
        if not line:
            return
        m = CURL.match(line)
        if m and self.downloading:                     # curl meter: only the percentage
            pct = int(m.group(1))
            GLib.idle_add(self.on_progress, 0.02 + 0.2 * pct / 100, f'Downloading Wine… {pct}%')
            return
        GLib.idle_add(self.on_log, line)
        if line.startswith('==> '):
            text = line[4:]
            self.downloading = text.startswith('Wine runner')
            for key, fraction, nice in STEPS:
                if key in text:
                    self.fraction = max(self.fraction, fraction)
                    GLib.idle_add(self.on_progress, self.fraction, nice)
                    return
            GLib.idle_add(self.on_progress, None, text)
