# SPDX-License-Identifier: GPL-3.0-only
"""Private local operator channel. Reuses the controller; never opens serial itself.

One JSON request/response per Unix connection. The socket and its directory are
private to the logged-in user. Session IDs, expiry and request IDs prevent stale
or repeated actuation. The public Python HTTP API is deliberately unchanged.
"""
import json
import math
import os
from pathlib import Path
import secrets
import socket
import socketserver
import stat
import threading
import time


class JarvisChannel:
    def __init__(self, controller, studio, folder, journal=None):
        self.c, self.s, self.journal = controller, studio, journal
        self.folder = Path(folder) / 'jarvis'
        self.path = self.folder / 'control.sock'
        self.session = secrets.token_urlsafe(24)
        self.server = None
        self.gate = threading.Lock()
        self.guard = threading.RLock()
        self.seen = set()
        self.cancelled = 0
        self.quit_requested = False
        self.connection_selection = None
        self.ui_time = 0.
        self.ui = dict(speed_pending=False, return_home=False)

    def update_ui(self, info=None):
        with self.guard:
            self.ui_time = time.monotonic()
            if isinstance(info, dict):
                self.ui = dict(speed_pending=info.get('speed_pending') is True,
                               return_home=info.get('return_home') is True)

    def take_connection_selection(self):
        with self.guard:
            selection = self.connection_selection
            self.connection_selection = None
            return selection

    def audit(self, kind, text):
        if self.journal:
            try:
                self.journal.add(kind, 'jarvis', text)
            except Exception:
                pass  # A full disk must never prevent STOP.

    def start(self):
        if os.name == 'nt' or not hasattr(socketserver, 'ThreadingUnixStreamServer'):
            # Private Unix socket with owner checks: macOS and Linux only for now.
            raise OSError('Canale JARVIS non disponibile su questo sistema.')
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Cartella del canale locale non valida.')
        self.folder.chmod(0o700)
        if self.path.exists() or self.path.is_symlink():
            info = self.path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError('Percorso del socket locale non valido.')
            # The native bridge already owns the exclusive controller lock.
            self.path.unlink()
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(4)
                try:
                    raw = self.rfile.readline(8193)
                    if len(raw) > 8192 or not raw.endswith(b'\n'):
                        raise ValueError('Richiesta troppo grande o incompleta.')
                    data = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Numero non valido.')))
                    result = owner.dispatch(data)
                except (ValueError, TypeError, KeyError, OSError) as error:
                    result = dict(ok=False, error=str(error), session=owner.session)
                    owner.audit('error', str(error))
                try:
                    self.wfile.write(json.dumps(result, allow_nan=False).encode() + b'\n')
                except OSError:
                    pass  # Never retry a command whose reply was lost.

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True
            block_on_close = False

        self.server = Server(str(self.path), Handler)
        self.path.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        self.thread.start()

    def close(self):
        with self.guard:
            self.cancelled += 1
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=1)
            self.server = None
            self.path.unlink(missing_ok=True)

    def snapshot(self):
        state = self.c.state()
        keys = ('mode', 'connected', 'identified', 'speed_confirmed', 'hardware_ok',
                'home', 'busy', 'playing', 'pos', 'limits', 'error', 'guidance',
                'operator_collision_checks', 'axes_enabled', 'ports')
        return dict(ok=True, version=1, session=self.session, epoch=self.cancelled, pid=os.getpid(),
                    state={key: state.get(key) for key in keys},
                    enabled_poses=[p['name'] for p in state['sequence'] if p.get('enabled', True)])

    def check_request(self, data, epoch):
        if epoch != self.cancelled or self.quit_requested:
            raise ValueError('Comando annullato da STOP o chiusura.')
        if data['expires'] < time.time():
            raise ValueError('Comando scaduto: nessuna ripetizione automatica.')
        if time.monotonic() - self.ui_time > 2:
            raise ValueError('Interfaccia Robot Console assente: comando rifiutato.')

    def dispatch(self, data):
        if not isinstance(data, dict):
            raise ValueError('Richiesta JSON non valida.')
        op = data.get('op')
        if op == 'status':
            return self.snapshot()
        if op not in ('enable', 'jog', 'sequence', 'home', 'stop', 'quit'):
            raise ValueError('Comando non disponibile sul canale JARVIS.')
        with self.guard:
            if data.get('session') != self.session:
                raise ValueError('Sessione cambiata: ripeti la richiesta a voce.')
            expires = data.get('expires')
            if type(expires) not in (float, int) or not math.isfinite(expires) or not time.time() <= expires <= time.time() + 30:
                raise ValueError('Comando scaduto o scadenza non valida.')
            key = data.get('id')
            if not isinstance(key, str) or not 16 <= len(key) <= 80 or key in self.seen:
                raise ValueError('Richiesta duplicata o identificativo non valido: non eseguita.')
            if op not in ('stop', 'quit') and len(self.seen) >= 10000:
                raise ValueError('Sessione del canale esaurita: riapri Robot Console.')
            if op not in ("stop", "quit") and data.get("epoch") != self.cancelled:
                raise ValueError("STOP intervenuto: richiesta scaduta.")
            if op not in ("stop", "quit"):
                self.seen.add(key)
            epoch = self.cancelled
        self.audit('request', json.dumps({k: v for k, v in data.items() if k != 'session'}, ensure_ascii=False))
        # STOP never waits for connection setup or planning and invalidates pending work.
        if op in ('stop', 'quit'):
            with self.c.lock, self.guard:
                self.cancelled += 1
                self.c.action(dict(op='stop'))
                if op == 'quit':
                    if self.c.firmware_busy:
                        raise ValueError('STOP inviato; attendi la fine dell’operazione firmware prima di chiudere.')
                    self.quit_requested = True
            return dict(ok=True, session=self.session, message='STOP ed esci richiesto.' if op == 'quit' else 'STOP inviato a Robot Console.')
        if not self.gate.acquire(blocking=False):
            raise ValueError('Un comando JARVIS è già in corso. Attendi oppure chiedi STOP.')
        try:
            with self.guard:
                self.check_request(data, epoch)
            if op == 'enable':
                result = self.enable(data, epoch)
            else:
                # Same lock order as Studio. Keep validation and dispatch atomic.
                with self.s.lock, self.c.lock, self.guard:
                    self.check_request(data, epoch)
                    if self.ui['speed_pending']:
                        raise ValueError('Applica o annulla le velocità modificate nella Console prima di muovere.')
                    self.c.check()
                    if self.c.busy or self.c.playing or self.c.firmware_busy:
                        raise ValueError('Robot occupato: nessun movimento accodato.')
                    result = self.jog(data) if op == 'jog' else self.home() if op == 'home' else self.sequence(data)
            self.audit('result', result)
            return dict(ok=True, session=self.session, message=result)
        finally:
            self.gate.release()

    def enable(self, data, epoch):
        if data.get('home_confirmed') is not True:
            raise ValueError('Manca la richiesta esplicita di abilitazione e riferimento HOME.')
        with self.c.lock, self.guard:
            self.check_request(data, epoch)
            if self.c.busy or self.c.playing or self.c.firmware_busy:
                raise ValueError('Robot occupato: abilitazione rifiutata.')
            if self.c.connected and self.c.mode != 'robot':
                raise ValueError('Anteprima già connessa: scollegala prima di abilitare il robot reale.')
            # Connected to the robot but the Mega never identified itself: start again from the port.
            if not self.c.connected or not self.c.identified:
                self.open_robot_port(reset=False)
            generation = self.c.generation
        deadline = time.monotonic() + 12
        reopened = False
        while True:
            with self.c.lock, self.guard:
                self.check_request(data, epoch)
                if self.c.generation != generation or not self.c.connected:
                    raise ValueError('Connessione interrotta: HOME non impostata.')
                if self.c.identified and self.c.speed_confirmed:
                    break
                now = time.monotonic()
                # Seen on 10 November: after a previous session the Mega stayed silent, not even
                # answering hello, until the port was opened again. Do it once, with a board reset.
                if not reopened and not self.c.identified and self.c.fd is not None and now >= self.c.boot_ready_at + 2.5:
                    self.c.log('La Mega non risponde: JARVIS riapre la USB una volta, con riavvio della scheda.')
                    self.open_robot_port(reset=True)
                    generation = self.c.generation
                    reopened = True
                    deadline = time.monotonic() + 9
                    continue
                if now >= deadline:
                    raise ValueError(self.c.error or 'La Mega non ha confermato firmware e velocità.')
            time.sleep(.05)
        # HOME only after the USB quiet window, when the heartbeat flows: the controller sends it only
        # from then on, and an earlier ARM trips the 1.5 s firmware watchdog (seen on 9 November).
        while self.c.fd is not None and time.monotonic() < self.c.boot_ready_at + .3:
            with self.guard:
                self.check_request(data, epoch)
            time.sleep(.05)
        limits = self.saved_limits()
        with self.s.lock, self.c.lock, self.guard:
            self.check_request(data, epoch)
            if self.c.generation != generation or self.c.mode != 'robot' or not self.c.connected:
                raise ValueError('Stato cambiato: abilitazione annullata.')
            if not self.c.home:
                self.c.action(dict(op='home_set'))
            self.c.check()
            # Existing personal protocol requests warnings only; connect resets it.
            self.s.action(dict(op='studio_operator_collisions', enabled=False, confirmed=True))
            applied = False
            if limits and all(lo == hi for lo, hi in self.c.limits):
                # The operator's last applied limits for the real robot (limiti.json), as the GUI would.
                self.c.action(dict(op='limits', limits=limits))
                self.c.log('Limiti ripristinati da JARVIS: ' + ' · '.join('J%d %g…%g' % (i + 1, lo, hi) for i, (lo, hi) in enumerate(limits)))
                applied = True
        if applied or not all(lo == hi for lo, hi in self.c.limits):
            return 'Robot abilitato, signore. Ultimi limiti applicati.'
        return 'Robot abilitato, signore. Quali limiti imposto?'

    def open_robot_port(self, reset):
        """Same as choosing Robot USB and pressing Connetti Mega. With reset, DTR is dropped and raised
        again: the Mega restarts as on every normal connection. Called with the controller lock held."""
        import serial_transport
        ports = [p for p in self.c.state()['ports'] if serial_transport.looks_like_board(p)]
        # Optional per-machine choice; nothing personal is hard-coded in the source.
        preferred = os.environ.get('ROBOT_CONSOLE_PORT', '')
        if preferred and preferred in ports:
            port = preferred
        elif len(ports) == 1:
            port = ports[0]
        else:
            raise ValueError('Mega non collegata.' if not ports else 'Più porte Mega presenti: selezione non univoca.')
        self.c.action(dict(op='connect', mode='robot', port=port))
        self.connection_selection = dict(mode='robot', port=port)
        if reset and self.c.fd is not None:
            import serial_transport
            serial_transport.pulse_reset(self.c.fd)
            # The quiet window restarts from the reset, so the bootloader is left alone.
            quiet = self.c.boot_ready_at - self.c.connected_at
            retry = self.c.connected_at - self.c.last_hello
            now = time.monotonic()
            self.c.connected_at, self.c.boot_ready_at, self.c.last_hello = now, now + quiet, now - retry

    def saved_limits(self):
        """Last limits applied to the real robot, validated like the native bridge does."""
        try:
            values = json.loads((self.folder.parent / 'limiti.json').read_text()).get('robot')
        except (OSError, ValueError, AttributeError):
            return None
        if not isinstance(values, list) or len(values) not in (5, 6):
            return None
        if not all(isinstance(pair, list) and len(pair) == 2
                   and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in pair)
                   and -360 <= pair[0] <= 0 <= pair[1] <= 360 for pair in values):
            return None
        return [list(map(float, pair)) for pair in values] + [[0., 0.]] * (6 - len(values))

    def home(self):
        """Same path as the "Vai a HOME…" button: plan the return, then run it. No token needed."""
        if all(abs(v) < .005 for v in self.c.pos):
            return 'Il robot è già in HOME, signore.'
        self.s.movej.prepare(dict(source='home'))
        context = self.s.movej.plan['controller_context']
        self.s.follow = True
        self.s.movej.running = False
        self.s.movej.visual_active = False
        self.c.action(dict(op='home', context=context))
        return 'Ritorno in HOME avviato, signore.'

    def jog(self, data):
        joint, value = data.get('joint'), data.get('degrees')
        if type(joint) is not int or not 1 <= joint <= 6:
            raise ValueError('Giunto non valido: usa J1–J6.')
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 360:
            raise ValueError('Angolo non valido.')
        if data.get('mode') not in ('relative', 'absolute'):
            raise ValueError('Specifica movimento relativo o assoluto.')
        axis = joint - 1
        if self.c.limits[axis][0] == self.c.limits[axis][1]:
            raise ValueError('Applica prima i limiti di J%d nella Console.' % joint)
        delta = value if data['mode'] == 'relative' else value - self.c.pos[axis]
        target = self.c.validate(axis, delta)
        if abs(delta) < .001:
            return 'J%d è già alla posizione richiesta.' % joint
        self.s.follow = True
        self.c.action(dict(op='jog', axis=axis, delta=delta))
        return 'Avviato J%d verso %g gradi, signore.' % (joint, target)

    def sequence(self, data):
        name = data.get('name')
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Nome posa non valido.')
            matches = [i for i, p in enumerate(self.c.sequence) if p['name'].casefold() == name.strip().casefold()]
            if len(matches) != 1:
                raise ValueError('Posa non trovata o nome duplicato: indica un nome univoco.')
            # Execute the named pose without editing the saved inclusion switches.
            self.s.follow = True
            self.c.action(dict(op='pose_start', index=matches[0]))
            return 'Posa %s avviata, signore.' % self.c.sequence[matches[0]]['name']
        names = [p['name'] for p in self.c.sequence if p.get('enabled', True)]
        if not names:
            raise ValueError('Abilita almeno una posa nella sequenza.')
        request = dict(source='sequence', return_home=self.ui['return_home'])
        self.s.movej.prepare(request)
        context = self.s.movej.plan['controller_context']
        self.s.follow = True
        self.s.movej.running = False
        self.s.movej.visual_active = False
        self.c.action(dict(op='play', context=context, repeat=False, return_home=self.ui['return_home']))
        return 'Sequenza avviata, signore: ' + ', '.join(names) + '.'
