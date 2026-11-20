# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Controller process client: one JSON request per line, exactly one reply per request.

The controller (native/native_bridge.py) owns the serial port. Closing its stdin is
the shutdown signal: it sends STOP to the robot and exits, so a crash of the window
can never leave a motion command running without supervision.
"""
import json, os, sys
from collections import deque
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

ROOT = Path(__file__).resolve().parents[1]


class Bridge(QObject):
    replied = Signal(str, dict, dict)  # op, request values, reply
    failed = Signal(str)

    def __init__(self, parent=None, environment=None):
        super().__init__(parent)
        self.pending = deque()
        self.buffer = b''
        self.closing = False
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ROOT))
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1')
        env.insert('PYTHONIOENCODING', 'utf-8')
        env.insert('PYTHONUTF8', '1')  # files are UTF-8 on every system (Windows defaults to cp1252)
        for key, value in (environment or {}).items():
            env.insert(key, value)
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)

    def start(self):
        if getattr(sys, 'frozen', False):
            # Packaged app: the bundled executable runs the controller itself.
            self.process.start(sys.executable, ['--controller'])
        else:
            self.process.start(sys.executable, ['-X', 'utf8', '-u', str(ROOT / 'native' / 'native_bridge.py')])
        if not self.process.waitForStarted(8000):
            self.failed.emit('Impossibile avviare il controllo: ' + self.process.errorString())
            return False
        return True

    def running(self):
        return self.process.state() == QProcess.Running and not self.closing

    def send(self, op, values=None, callback=None, extra=None):
        if not self.running():
            if callback:
                callback(False, {})
            return False
        request = dict(values or {})
        request['op'] = op
        request.update(extra or {})
        try:
            line = json.dumps(request, ensure_ascii=False).encode('utf-8') + b'\n'
        except (TypeError, ValueError):
            if callback:
                callback(False, {})
            return False
        self.pending.append((op, values or {}, callback))
        self.process.write(line)
        return True

    def busy_with(self, op):
        return any(item[0] == op for item in self.pending)

    def _read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if not line.strip():
                continue
            try:
                reply = json.loads(line.decode('utf-8', errors='replace'))
            except ValueError:
                continue
            if not self.pending:
                # Unsolicited line: only the startup refusal ("already open") is expected.
                if reply.get('error'):
                    self.failed.emit(reply['error'])
                continue
            op, values, callback = self.pending.popleft()
            self.replied.emit(op, values, reply)
            if callback:
                callback(reply.get('error') is None, reply)

    def _finished(self, *_):
        pending, self.pending = list(self.pending), deque()
        for _op, _values, callback in pending:
            if callback:
                callback(False, {})
        if not self.closing:
            error = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
            self.failed.emit('Controllo locale terminato.' + (' ' + error.splitlines()[-1] if error else ''))

    def _error(self, error):
        if error == QProcess.FailedToStart:
            self.failed.emit('Impossibile avviare Python per il controllo locale.')

    def close(self, timeout=4000):
        """Ask for STOP, close stdin (the controller halts and exits) and wait."""
        if self.process.state() == QProcess.NotRunning:
            return
        if not self.closing:
            self.send('stop')
        self.closing = True
        self.process.waitForBytesWritten(1000)
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(timeout):
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
