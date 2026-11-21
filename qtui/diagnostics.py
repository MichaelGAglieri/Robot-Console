# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Diagnostics: telemetry chart, sensors, digital outputs, ROS 2, local Python API, camera."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFileDialog, QLabel, QSizePolicy, QVBoxLayout, QWidget
from .i18n import F, T
from .model import parse_int
from .widgets import Card, Disclosure, button, caption, checkbox, clear_layout, combo, label, line, row, set_combo_items, set_role, hline
from . import theme

SERIES = ['#A3EA2F', '#3E8EF7', '#FFB020', '#E5484D', '#B07CF0', '#2FC4B2']
TOOL_NAMES = dict(rviz='RViz 2', gazebo='Gazebo · scena di esempio', webots='Webots · laboratorio', bag='Registrazione rosbag')


class TelemetryChart(QWidget):
    """Joint angles over time, one line per joint (like the Swift Charts view)."""

    def __init__(self):
        super().__init__()
        self.points = []
        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_points(self, points):
        if points != self.points:
            self.points = points
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(44, 8, -70, -22)
        p.setPen(QPen(theme.color('border'), 1))
        p.drawRect(rect)
        if len(self.points) < 2:
            return
        times = [pt['time'] for pt in self.points]
        values = [v for pt in self.points for v in pt['values'][:6]]
        t0, t1 = min(times), max(times)
        lo, hi = min(values), max(values)
        if hi - lo < 1:
            lo, hi = lo - .5, hi + .5
        span_t = max(t1 - t0, 1e-6)
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)
        p.setPen(theme.color('secondary'))
        for frac in (0, .5, 1):
            y = rect.bottom() - frac * rect.height()
            p.drawText(0, int(y) - 6, 40, 12, Qt.AlignRight | Qt.AlignVCenter, '%.0f°' % (lo + frac * (hi - lo)))
        p.drawText(rect.left(), rect.bottom() + 4, 120, 14, Qt.AlignLeft, '-%.0f s' % span_t)
        p.drawText(rect.right() - 60, rect.bottom() + 4, 60, 14, Qt.AlignRight, '0 s')
        count = min(6, min(len(pt['values']) for pt in self.points))
        for axis in range(count):
            path = QPainterPath()
            for i, pt in enumerate(self.points):
                x = rect.left() + (pt['time'] - t0) / span_t * rect.width()
                y = rect.bottom() - (pt['values'][axis] - lo) / (hi - lo) * rect.height()
                (path.moveTo if i == 0 else path.lineTo)(QPointF(x, y))
            p.setPen(QPen(QColor(SERIES[axis]), 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            ly = rect.top() + axis * 16
            p.drawLine(rect.right() + 10, ly + 6, rect.right() + 24, ly + 6)
            p.setPen(theme.color('text'))
            p.drawText(rect.right() + 28, ly, 40, 12, Qt.AlignLeft | Qt.AlignVCenter, 'J%d' % (axis + 1))


class OutputIOPanel(QWidget):
    def __init__(self, m):
        super().__init__()
        self.m = m
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.name = line('Nome uscita', 170)
        self.define = button('Definisci uscita', None, lambda: m.send('studio_output_add', dict(name=self.name.text())))
        layout.addWidget(hline())
        layout.addLayout(row(label('Uscite digitali e adattatori', 'section'), None, self.name, self.define))
        self.items = QVBoxLayout()
        layout.addLayout(self.items)
        layout.addWidget(caption('Le uscite si comandano come istruzioni di programma. In Anteprima sono simulate; sul robot serve la conferma dell’adattatore entro il timeout. Nessuna uscita GPIO della Mega viene modificata.'))
        self.key = None

    def refresh(self):
        self.define.setEnabled(self.m.idle and bool(self.name.text().strip()))
        io = (self.m.studio or {}).get('io') or {}
        key = repr(io)
        if key == self.key:
            return
        self.key = key
        clear_layout(self.items)
        for o in io.get('outputs') or []:
            value = '—' if o.get('value') is None else ('1' if o['value'] else '0')
            self.items.addLayout(row(label(o['name'], 'section'), label(value, 'mono'),
                                     caption('Simulata' if o.get('simulated') else 'Confermata dall’adattatore'), caption(o.get('source', '')), None))
        for a in io.get('adapters') or []:
            self.items.addLayout(row(label(a['name'], 'section'), caption('Simulato' if a.get('simulated') else 'Dichiarato misurato'),
                                     label('Heartbeat attivo' if a.get('alive') else 'Heartbeat scaduto', 'accent' if a.get('alive') else 'warning'), None))
        for r in (io.get('requests') or [])[-5:]:
            self.items.addLayout(row(label(r['name']), label('1' if r.get('value') else '0', 'mono'), caption(r.get('status', '')), None))


class TelemetryPanel(Card):
    def __init__(self, m, window):
        super().__init__('Diagnostica · registrazioni e sensori')
        self.m, self.window = m, window
        self.origin = caption()
        self.record = checkbox('Registra sessione')
        self.record.clicked.connect(lambda v: m.send('studio_record', dict(enabled=v)))
        self.count = caption()
        self.export = button('Esporta CSV…', None, self.export_csv)
        self.add(row(self.origin, None, self.record, self.count, self.export))
        self.chart = TelemetryChart()
        self.add(self.chart)
        self.sensor_name = line('Nome ingresso', text='contatto_pinza')
        self.sensor_kind = combo([(k, k) for k in ('digital', 'distance', 'force', 'encoder', 'temperature')])
        self.add(row(self.sensor_name, label('Tipo'), self.sensor_kind,
                     button('Definisci sensore', None, lambda: m.send('studio_sensor_add', dict(name=self.sensor_name.text(), kind=self.sensor_kind.currentData())))))
        self.sensors = QVBoxLayout()
        self.add(self.sensors)
        self.add(caption('I dati sintetici sono marcati come simulati e non soddisfano attese di sensori sul robot reale. Gli encoder e gli altri sensori richiedono un adattatore connesso e dati aggiornati.'))
        self.io = OutputIOPanel(m)
        self.add(self.io)
        self.sensor_key = None

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self.window, T('Esporta CSV…'), 'robot-session.csv', 'CSV (*.csv)')
        if path:
            self.m.send('studio_export_csv', dict(path=path))

    def refresh(self):
        m, s = self.m, self.m.studio
        if not s:
            return
        self.origin.setText(T('Origine: ') + T('virtuale' if m.state.get('mode') == 'demo' else 'impulsi comandati · senza encoder'))
        self.record.setChecked(bool(s.get('recording')))
        self.count.setText(F('%lld campioni', s.get('sample_count', 0)))
        self.export.setEnabled(bool(s.get('sample_count')))
        telemetry = s.get('telemetry') or []
        self.chart.setVisible(bool(telemetry))
        self.chart.set_points(telemetry)
        demo = m.state.get('mode') == 'demo'
        key = (repr(s.get('sensors')), demo)
        if key != self.sensor_key:
            self.sensor_key = key
            clear_layout(self.sensors)
            for sensor in s.get('sensors') or []:
                value = sensor.get('value')
                text = '—' if value is None else ('1' if value is True else '0' if value is False else '%g' % value)
                age = sensor.get('age', -1)
                items = [label(sensor['name'], 'section'), caption(sensor.get('kind', '')), label(text, 'mono'), caption(sensor.get('source', '')), None,
                         caption(T('Nessun dato') if age < 0 else '%.1f s' % age)]
                if demo:
                    items += [button('Simula 0', None, lambda _c=False, n=sensor['name']: m.send('studio_sensor_value', dict(name=n, value=0))),
                              button('Simula 1', None, lambda _c=False, n=sensor['name']: m.send('studio_sensor_value', dict(name=n, value=1)))]
                self.sensors.addLayout(row(*items))
        self.io.refresh()


class LocalAPIPanel(QWidget):
    def __init__(self, m):
        super().__init__()
        self.m = m
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.toggle = button('Avvia API locale', None, self._toggle)
        layout.addWidget(hline())
        layout.addLayout(row(label('API Python · programmi e I/O', 'section'), None, self.toggle))
        self.url = label('', 'mono', selectable=True)
        self.copy = button('Copia token di questa sessione', None, self._copy)
        self.motion = checkbox('Consenti pianificazione dei programmi da API')
        self.demo = checkbox('Consenti esecuzione da script in Anteprima')
        self.motion.clicked.connect(lambda v: m.send('api_permissions', dict(enabled=v, demo_execution=self.demo.isChecked())))
        self.demo.clicked.connect(lambda v: m.send('api_permissions', dict(enabled=self.motion.isChecked(), demo_execution=v)))
        self.active = caption()
        self.stop_script = button('STOP script', 'danger', lambda: m.send('studio_cancel'))
        self.running_box = QWidget()
        box = QVBoxLayout(self.running_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.url)
        box.addLayout(row(self.copy, None))
        box.addWidget(self.motion)
        box.addWidget(self.demo)
        box.addLayout(row(self.active, self.stop_script, None))
        layout.addWidget(self.running_box)
        layout.addWidget(caption('Permessi disattivati a ogni avvio API. Sul robot reale ogni esecuzione richiede conferma nell’app. Solo 127.0.0.1 e token di sessione; nessun comando USB, firmware, HOME o limiti. Script assente per 3 s: STOP, senza ripresa automatica.'))

    def _toggle(self):
        api = self.m.local_api or {}
        self.m.send('api_stop' if api.get('running') else 'api_start')

    def _copy(self):
        QGuiApplication.clipboard().setText((self.m.local_api or {}).get('token', ''))
        self.m.set_message(T('Token copiato negli appunti.'))

    def refresh(self):
        api = self.m.local_api
        self.setVisible(api is not None)
        if not api:
            return
        running = bool(api.get('running'))
        self.toggle.setText(T('Ferma API' if running else 'Avvia API locale'))
        self.running_box.setVisible(running)
        self.url.setText(api.get('url', ''))
        self.motion.setChecked(bool(api.get('motion_enabled')))
        self.demo.setChecked(bool(api.get('demo_execution')))
        self.demo.setEnabled(bool(api.get('motion_enabled')))
        active = api.get('active')
        self.active.setVisible(bool(active))
        self.stop_script.setVisible(bool(active))
        if active:
            self.active.setText(F('Script in esecuzione: %@', active.get('name', '')))


class ROSPanel(Card):
    def __init__(self, m, window):
        super().__init__('ROS 2 · connessione, strumenti e API')
        self.m, self.window = m, window
        self.status = label('', 'accent')
        self.add(row(self.status, None, caption('Solo osservazione e visualizzazione')))
        self.project = line('Progetto ROS/Pixi', text=m.project_path)
        self.project.editingFinished.connect(lambda: m.set_project_path(self.project.text()))
        self.domain = line('42', 72, str(m.settings.value('rosDomain', 42, int)))
        self.add(row(self.project, button('Scegli cartella…', None, self.choose), label('Dominio'), self.domain,
                     button('Collega ROS 2', None, self.connect_ros), button('Scollega', None, lambda: m.send('ros_disconnect'))))
        self.add(caption('Il collegamento pubblica /robot_console/joint_states, /robot_console/robot_description e TF con prefisso robot_console/. Il modello segue l’anteprima o gli angoli stimati, secondo la modalità scelta. Nessun comando motore viene ricevuto da ROS.'))
        self.health = caption()
        self.topics = label('', 'mono')
        self.error = label('', 'stop')
        self.event = caption()
        self.add(self.health, self.topics, self.error, self.event)
        tools = Disclosure('Strumenti opzionali e integrazioni')
        tools.add(row(button('Rileva strumenti nel progetto', None, self.check_tools), None))
        self.tools = QVBoxLayout()
        tools.add(self.tools)
        tools.add(caption('RViz apre il modello della console; Webots mantiene il laboratorio dimostrativo separato. Gazebo apre una scena di esempio: un modello fisico calibrato richiede masse, inerzie e controllori appropriati. Gli strumenti non sono scaricati automaticamente e i log restano locali.'))
        self.add(tools)
        self.api = LocalAPIPanel(m)
        self.add(self.api)
        self.tools_key = None

    def choose(self):
        path = QFileDialog.getExistingDirectory(self.window, T('Scegli cartella…'), self.project.text())
        if path:
            self.project.setText(path)
            self.m.set_project_path(path)
            self.check_tools()

    def check_tools(self):
        self.m.set_project_path(self.project.text())
        self.m.send('tool_check', dict(project=self.m.project_path))

    def domain_value(self):
        return parse_int(self.domain.text(), 0, 232)

    def connect_ros(self):
        value = self.domain_value()
        if value is None:
            self.m.set_message(T('Dominio ROS ammesso: 0–232.'))
            return
        self.m.settings.setValue('rosDomain', value)
        self.m.set_project_path(self.project.text())
        self.m.send('ros_connect', dict(project=self.m.project_path, domain=value))
        self.check_tools()

    def refresh(self):
        m = self.m
        h = m.ros_health or {}
        self.status.setText(T(h.get('status') or 'Disconnesso'))
        running = bool(h.get('running'))
        self.health.setVisible(running)
        self.topics.setVisible(running)
        if running:
            self.health.setText(F('Heartbeat: %.1f s', h.get('age', 0)) + '   ' + T('Nodi: ') + ', '.join(h.get('nodes') or []))
            self.topics.setText('\n'.join(F('%@ · %.1f s dall’ultimo dato', t['name'], t['age']) for t in h.get('topics') or []))
        self.error.setVisible(bool(running and h.get('error')))
        self.error.setText(T(h.get('error') or ''))
        self.event.setText(T(m.ros_event))
        tools = m.tools or {}
        key = repr(tools)
        if key != self.tools_key:
            self.tools_key = key
            clear_layout(self.tools)
            for tool in tools.get('tools') or []:
                name = tool['name']
                state = ('Avviato dalla console' if tool.get('running') else 'Disponibile') if tool.get('available') else 'Non rilevato'
                start = button('Avvia', None, lambda _c=False, n=name: m.send('tool_start', dict(name=n, project=m.project_path, domain=self.domain_value() or 42)))
                stop = button('Ferma', None, lambda _c=False, n=name: m.send('tool_stop', dict(name=n)))
                start.setEnabled(bool(tool.get('available') and not tool.get('running')))
                stop.setEnabled(bool(tool.get('running')))
                title = label(TOOL_NAMES.get(name, name))
                title.setMinimumWidth(230)
                self.tools.addLayout(row(title, caption(state), None, start, stop))
            if tools.get('error'):
                self.tools.addWidget(label(tools['error'], 'warning'))
        self.api.refresh()


class CameraPanel(Card):
    """Local camera through QtMultimedia; QR decoding with OpenCV when it is installed."""

    def __init__(self, m, window):
        super().__init__('Visione · telecamera locale')
        self.m, self.window = m, window
        self.status = caption('Telecamera spenta')
        self.toggle = button('Avvia video', None, self._toggle)
        self.add(row(self.status, None, self.toggle))
        group = Disclosure('Video, fotogrammi e codici')
        self.add(group)
        self.devices = combo([])
        self.save = button('Salva fotogramma…', None, self.save_frame)
        self.qr = button('Rileva QR', None, self.detect)
        group.add(row(label('Telecamera'), self.devices, button('Aggiorna dispositivi', None, self.refresh_devices), self.save, self.qr, None))
        self.video = None
        self.video_box = QVBoxLayout()
        group.add(self.video_box)
        self.codes = label('', 'mono', selectable=True)
        group.add(self.codes)
        group.add(caption('Video e riconoscimento QR sono locali. Il contenuto rilevato viene mostrato come dato e non esegue comandi. Calibrazione ottica, AprilTag e stima 3D degli oggetti richiedono ulteriori modelli e un adattatore di visione.'))
        self.session = self.camera = self.sink = None
        self.frame = None
        self.available = True
        try:
            from PySide6 import QtMultimedia  # noqa: F401
        except ImportError:
            self.available = False
            self.status.setText(T('QtMultimedia non disponibile in questa installazione di PySide6.'))
        self.refresh_devices()
        self.running = False

    def refresh_devices(self):
        if not self.available:
            return
        from PySide6.QtMultimedia import QMediaDevices
        devices = QMediaDevices.videoInputs()
        set_combo_items(self.devices, [(bytes(d.id()).decode(errors='replace'), d.description()) for d in devices], self.devices.currentData())

    def _toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not self.available:
            return
        from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
        from PySide6.QtMultimediaWidgets import QVideoWidget
        device = next((d for d in QMediaDevices.videoInputs() if bytes(d.id()).decode(errors='replace') == self.devices.currentData()), None)
        if device is None:
            self.status.setText(T('Nessuna telecamera disponibile.'))
            return
        if self.video is None:
            self.video = QVideoWidget()
            self.video.setFixedHeight(260)
            self.video_box.addWidget(self.video)
        self.session = QMediaCaptureSession()
        self.camera = QCamera(device)
        self.camera.errorOccurred.connect(lambda _e, text: self.status.setText(text))
        self.session.setCamera(self.camera)
        self.session.setVideoOutput(self.video)
        self.sink = self.video.videoSink()
        self.sink.videoFrameChanged.connect(self._frame)
        self.camera.start()
        self.running = True
        self.video.show()
        self.status.setText(T('Video locale · ') + device.description())
        self.refresh()

    def _frame(self, frame):
        self.frame = frame

    def stop(self):
        if self.camera:
            self.camera.stop()
        if self.video:
            self.video.hide()
        self.session = self.camera = None
        self.frame = None
        self.running = False
        self.status.setText(T('Telecamera spenta'))
        self.refresh()

    def image(self):
        if self.frame is None or not self.frame.isValid():
            return None
        image = self.frame.toImage()
        return None if image.isNull() else image

    def save_frame(self):
        image = self.image()
        if image is None:
            self.status.setText(T('Avvia prima la telecamera.'))
            return
        path, _ = QFileDialog.getSaveFileName(self.window, T('Salva fotogramma…'), 'robot-camera.png', 'PNG (*.png)')
        if path:
            self.status.setText(T('Fotogramma salvato.') if image.save(path, 'PNG') else T('Salvataggio non riuscito.'))

    def detect(self):
        image = self.image()
        if image is None:
            self.status.setText(T('Avvia prima la telecamera.'))
            return
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.codes.setText(T('Per il riconoscimento QR installa opencv-python (facoltativo).'))
            return
        from PySide6.QtGui import QImage
        rgb = image.convertToFormat(QImage.Format_RGB888)
        data = np.frombuffer(rgb.constBits(), np.uint8).reshape(rgb.height(), rgb.bytesPerLine())[:, :rgb.width() * 3]
        found, decoded, _points, _ = cv2.QRCodeDetector().detectAndDecodeMulti(data.reshape(rgb.height(), rgb.width(), 3))
        codes = [c for c in (decoded or []) if c] if found else []
        self.codes.setText('\n'.join(codes) if codes else T('Nessun codice QR rilevato.'))

    def refresh(self):
        self.toggle.setText(T('Ferma video' if self.running else 'Avvia video'))
        self.toggle.setEnabled(self.available)
        self.devices.setEnabled(not self.running)
        self.save.setEnabled(self.running)
        self.qr.setEnabled(self.running)
