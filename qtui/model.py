# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Application state mirrored from the controller, plus the operator actions.

Same behaviour as the Regia model of the macOS app: a 0.4 s heartbeat, every reply
replaces the state, errors are shown in the warning banner, nothing moves without an
explicit operator action.
"""
import math
from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from .bridge import Bridge
from .i18n import T, language

EMPTY_STATE = dict(mode='demo', connected=False, home=False, pos=[0.0] * 6, limits=[[0.0, 0.0]] * 6, trail=0, sequence=[],
                   events=[], busy=False, playing=False, paused=False, error='', grip='non comandata', cycle=0, ports=[],
                   can_undo=False, max_speed=20.0, sequence_revision=0, identified=False, firmware='', speed=5.0,
                   speed_confirmed=False, guidance='1 · Avvia Anteprima per provare senza hardware.', robot_events=[])


def parse_number(text):
    """Draft text -> float, accepting comma and the typographic minus; None when invalid."""
    value = (text or '').strip().replace('−', '-').replace(',', '.')
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_int(text, low, high):
    value = (text or '').strip().replace('−', '-')
    try:
        number = int(value)
    except ValueError:
        return None
    return number if low <= number <= high else None


class AppModel(QObject):
    updated = Signal()
    message_changed = Signal(str)
    quit_ready = Signal()

    def __init__(self, environment=None):
        super().__init__()
        self.settings = QSettings('DOC', 'Robot Console')
        self.state = dict(EMPTY_STATE)
        self.studio = None
        self.firmware = dict(available=False, tool='', busy=False, phase='idle', status='Verifica strumenti firmware…',
                             error='', logs=[], boards=[], success=False)
        self.firmware_workspace = None
        self.firmware_file = 'RegiaDemo.ino'
        self.firmware_text = ''
        self.ollama = dict(installed=False, running=False, busy=False, status='Verifica Ollama…', error='', version='',
                           models=[], loaded=[], selected='')
        self.ros_health = None
        self.tools = None
        self.local_api = None
        self.chat = []
        self.diary = []
        self.assistant_busy = False
        self.ros_status = 'Disconnesso'
        self.ros_event = ''
        self.last_limits = {}
        self.home_preview = None
        self.home_revision = 0
        self.multi_plan = None
        self.multi_revision = 0
        self.voice_command = None
        self.message = 'Avvio del controllo locale…'
        # Operator drafts (never overwritten by the heartbeat).
        self.mode = 'demo'
        self.port = ''
        self.step = 1.0
        self.speed_edits = set()
        self.multi_mode = False
        self.sequence_return_home = False
        self.show_extra_joints = False
        self.keyboard_axis = 0
        self.keyboard_enabled = True
        self.project_path = self.settings.value('rosProjectPath', '', str)
        self.returning_to_quit = False
        self.return_request_accepted = False
        self.jarvis_quitting = False
        self.pending_poll = False
        self.alive = False
        self.bridge = Bridge(self, environment)
        self.bridge.replied.connect(self._replied)
        self.bridge.failed.connect(self._failed)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.poll)

    # --- transport -----------------------------------------------------------------
    def start(self):
        if self.bridge.start():
            self.alive = True
            self.timer.start()
            self.poll()

    def poll(self):
        if not self.pending_poll and self.alive:
            self.pending_poll = True
            self.send('heartbeat', poll=True)

    def send(self, op, values=None, callback=None, poll=False):
        extra = dict(language=language(),
                     jarvis_ui=dict(speed_pending=bool(self.speed_edits), return_home=self.sequence_return_home))

        def done(ok, reply):
            if poll:
                self.pending_poll = False
            if callback:
                callback(ok, reply)
        sent = self.bridge.send(op, values, done, extra)
        if not sent and poll:
            self.pending_poll = False
        return sent

    def _replied(self, op, values, reply):
        if reply.get('state') is not None:
            self.state = dict(EMPTY_STATE, **reply['state'])
        connection = reply.get('jarvis_connection')
        if connection:
            self.mode = connection.get('mode', self.mode)
            self.port = connection.get('port', self.port)
        if reply.get('home_preview') is not None and values.get('revision') == self.home_revision:
            self.home_preview = reply['home_preview']
        if reply.get('multi_plan') is not None and values.get('revision') == self.multi_revision:
            self.multi_plan = reply['multi_plan']
        if reply.get('voice_command') is not None:
            self.voice_command = reply['voice_command']
        for key, attribute in (('studio', 'studio'), ('firmware_workspace', 'firmware_workspace'), ('ros_health', 'ros_health'),
                               ('tools', 'tools'), ('local_api', 'local_api'), ('firmware_text', 'firmware_text'),
                               ('firmware_file', 'firmware_file'), ('ollama', 'ollama'), ('firmware', 'firmware'),
                               ('last_limits', 'last_limits'), ('chat', 'chat'), ('diary', 'diary')):
            if reply.get(key) is not None:
                setattr(self, attribute, reply[key])
        self.assistant_busy = bool(reply.get('assistant_busy'))
        self.ros_status = reply.get('ros_status') or 'Disconnesso'
        self.ros_event = reply.get('ros_event') or ''
        error = reply.get('error')
        if error:
            self.set_message(error)
            if op in ('home', 'end_cycle'):
                self.returning_to_quit = False
        elif op != 'heartbeat' or self.message == 'Avvio del controllo locale…':
            self.set_message('')
        if reply.get('jarvis_quit') and not self.jarvis_quitting:
            self.jarvis_quitting = True
            self.quit_ready.emit()
        if op == 'home' and not error and self.returning_to_quit:
            self.return_request_accepted = True
        self.updated.emit()

    def _failed(self, text):
        self.alive = False
        self.timer.stop()
        self.set_message(text)
        self.updated.emit()

    def set_message(self, text):
        if text != self.message:
            self.message = text
            self.message_changed.emit(text)

    # --- derived state ---------------------------------------------------------------
    @property
    def idle(self):
        return not self.state.get('busy') and not self.state.get('playing')

    @property
    def zero(self):
        return self.state.get('home') and all(abs(v) < .01 for v in self.state.get('pos', []))

    def connection_status(self):
        s = self.state
        if not s.get('connected'):
            return 'Non connesso'
        if not s.get('identified'):
            return 'Porta USB aperta · firmware da verificare'
        if not s.get('speed_confirmed'):
            return 'Verifica velocità'
        if not s.get('home'):
            return 'Conferma HOME'
        return 'Movimento in corso' if s.get('busy') else 'Pronto'

    def control_axes(self):
        if self.show_extra_joints:
            return list(range(6))
        mapping = (self.studio or {}).get('mapping') or {}
        mapped = sorted({v for v in mapping.values() if isinstance(v, int) and 0 <= v < 6})
        return mapped or list(range(5))

    def can_jog(self, axis, sign):
        s = self.state
        if not (s.get('connected') and s.get('identified') and s.get('speed_confirmed') and s.get('home') and self.idle
                and not self.firmware.get('busy')):
            return False
        if (s.get('axes_available') or [True] * 6)[axis] is False or (s.get('axes_enabled') or [True] * 6)[axis] is False:
            return False
        if s.get('hardware_ok') is False:
            return False
        target = s['pos'][axis] + sign * self.step
        low, high = s['limits'][axis]
        return low <= target <= high

    def limits_mode(self):
        return self.state['mode'] if self.state.get('connected') else self.mode

    # --- actions -----------------------------------------------------------------------
    def connect_now(self):
        self.send('connect', dict(mode=self.mode, port=self.port))

    def jog(self, axis, sign):
        if self.can_jog(axis, sign):
            self.send('jog', dict(axis=axis, delta=sign * self.step))

    def keyboard_jog(self, sign):
        if self.keyboard_enabled and not self.multi_mode and self.keyboard_axis in self.control_axes():
            self.jog(self.keyboard_axis, sign)

    def stop(self):
        self.send('stop')

    def plan(self, source, callback, **values):
        if self.speed_edits:
            self.set_message(T('Applica le velocità modificate prima di pianificare.'))
            return
        self.send('studio_movej_plan', dict(source=source, **values), callback)

    def plan_context(self):
        playback = (self.studio or {}).get('movej_preview') or {}
        return (playback.get('plan') or {}).get('controller_context')

    def request_multi_plan(self, drafts):
        self.multi_revision += 1
        self.multi_plan = None
        if not self.multi_mode:
            return
        values = [parse_number(d) for d in drafts]
        if not all(v is not None and abs(v) <= 360 for v in values):
            self.multi_plan = dict(valid=False, error=T('Inserisci sei angoli validi da −360° a +360°.'), deltas=[], axes=[],
                                   peaks=[], duration=0, budget_limited=False)
            self.updated.emit()
            return
        self.send('multi_preview', dict(deltas=values, revision=self.multi_revision))

    def set_project_path(self, path):
        self.project_path = path
        self.settings.setValue('rosProjectPath', path)

    def shutdown(self):
        self.timer.stop()
        self.alive = False
        self.bridge.close()
