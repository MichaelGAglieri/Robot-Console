# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Studio 3D: arm view, model setup, work scene, Cartesian IK, MoveJ preview, programs, validation."""
import json, math
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QPlainTextEdit, QSlider, QVBoxLayout,
                               QWidget)
from .i18n import F, T
from .model import parse_int, parse_number
from .viewport3d import ArmView
from .widgets import (Card, Disclosure, Segmented, button, caption, checkbox, clear_layout, combo, confirm, label, line, row,
                      select_combo, set_combo_items, set_role, well)
from . import theme

VIEWS = [('perspective', '3D'), ('front', 'Fronte'), ('side', 'Lato'), ('top', 'Alto')]


def movable(studio):
    return [j for j in studio['model']['joints'] if j.get('kind') != 'fixed' and not j.get('mimic')]


def rotary(joint):
    return joint.get('kind') != 'prismatic'


def multiplier(joint):
    return 180 / math.pi if rotary(joint) else 1000.0


def ready(m):
    studio = m.studio or {}
    playback = studio.get('movej_preview') or {}
    return m.idle and not m.firmware.get('busy') and not studio.get('program_running') and not playback.get('executing')


def angles_text(values, digits=1):
    return ' · '.join(('J%d %.' + str(digits) + 'f°') % (i + 1, v) for i, v in enumerate(list(values)[:6]))


class TimeSlider(QSlider):
    """Scrubber over a plan: pressing stops the preview, releasing seeks the plan."""

    def __init__(self, m):
        super().__init__(Qt.Horizontal)
        self.m = m
        self.setRange(0, 1000)
        self.duration = 0.0
        self.plan_id = None
        self.sliderPressed.connect(lambda: self.m.send('studio_movej_stop'))
        self.sliderReleased.connect(self._seek)

    def seconds(self):
        return self.value() / 1000 * self.duration

    def _seek(self):
        if self.plan_id:
            self.m.send('studio_movej_seek', dict(id=self.plan_id, elapsed=min(self.seconds(), self.duration)))

    def show_plan(self, plan, playback):
        self.plan_id, self.duration = plan.get('id'), max(plan.get('duration', 0), .001)
        self.setEnabled(bool(playback.get('valid')))
        if not self.isSliderDown():
            self.blockSignals(True)
            self.setValue(int(round(min(playback.get('elapsed', 0), self.duration) / self.duration * 1000)))
            self.blockSignals(False)


class ViewHeightGrip(QFrame):
    """Drag to resize the 3D viewport only; double click restores 440 px."""

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.setFixedHeight(14)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip(T('Trascina per cambiare l’altezza della vista 3D. Doppio clic per ripristinarla.'))
        self.start = None

    def paintEvent(self, _event):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.color('border'))
        p.drawRoundedRect(self.width() / 2 - 24, 4, 48, 5, 2.5, 2.5)

    def mousePressEvent(self, event):
        self.start = (event.globalPosition().y(), self.target.height())

    def mouseMoveEvent(self, event):
        if self.start:
            self.target.setFixedHeight(int(min(900, max(280, self.start[1] + event.globalPosition().y() - self.start[0]))))

    def mouseReleaseEvent(self, _event):
        self.start = None

    def mouseDoubleClickEvent(self, _event):
        self.target.setFixedHeight(440)


class ArmPanel(QFrame):
    """ArmMiniView: the 3D arm with its view controls."""

    def __init__(self, m, window, compact=False):
        super().__init__()
        self.m, self.window = m, window
        self.setObjectName('Well')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.follow = checkbox('Segui comandi')
        self.follow.clicked.connect(lambda v: m.send('studio_follow', dict(enabled=v)))
        layout.addLayout(row(label('Anteprima 3D', 'headline', wrap=False), None, self.follow))
        self.home_button = button('HOME del modello…', None, lambda: ModelHomeEditor(m, window).exec())
        layout.addLayout(row(self.home_button, None))
        self.home_note = caption('La HOME del modello modifica solo la vista 3D: il riferimento del controllore resta valido.', small=True)
        layout.addWidget(self.home_note)
        self.view = ArmView()
        layout.addLayout(row(button('Adatta vista', None, self.view.fit), button('↺', None, lambda: self.view.rotate(-1), 'Ruota a sinistra'),
                             button('↻', None, lambda: self.view.rotate(1), 'Ruota a destra'), None))
        self.count = caption()
        layout.addWidget(self.count)
        if compact:
            layout.addWidget(self.view, 1)
        else:
            self.view.setFixedHeight(440)
            layout.addWidget(self.view)
            layout.addWidget(ViewHeightGrip(self.view))
        self.trace = QWidget()
        self.trace_time = label('', 'mono')
        self.trace_play = button('▶ MoveJ', None, self._play, 'Riproduci anteprima')
        self.trace_stop = button('■ MoveJ', 'danger', lambda: m.send('studio_movej_stop'), 'Arresta anteprima')
        self.trace.setLayout(row(label('Traccia arancione · MoveJ', 'accent'), None, self.trace_time, self.trace_play, self.trace_stop))
        layout.addWidget(self.trace)
        layout.addWidget(caption('Trascina: ruota · Maiusc + trascina: sposta · rotella o pizzico: zoom', small=True))
        self.views = Segmented(VIEWS)
        self.views.changed.connect(self.view.set_preset)
        layout.addWidget(self.views)
        self.follow_note = caption(small=True)
        self.tcp = label('', 'mono')
        self.collisions = label('', 'stop')
        layout.addWidget(self.follow_note)
        layout.addWidget(self.tcp)
        layout.addWidget(self.collisions)

    def _play(self):
        plan = ((self.m.studio or {}).get('movej_preview') or {}).get('plan') or {}
        self.m.send('studio_movej_play', dict(id=plan.get('id')))

    def refresh(self):
        m, s = self.m, self.m.studio
        if not s:
            self.count.setText(T('Caricamento modello…'))
            return
        self.follow.setChecked(bool(s.get('follow')))
        playback = s.get('movej_preview') or {}
        self.home_button.setEnabled(m.idle and not m.firmware.get('busy') and not playback.get('running'))
        self.home_note.setVisible(bool(m.state.get('connected')))
        self.count.setText(F('%lld giunti mobili nel modello', len(movable(s))))
        grip = playback.get('grip') or m.state.get('grip') if playback.get('visual_active') else m.state.get('grip')
        self.view.update_studio(s, grip or '')
        plan = playback.get('plan') or {}
        self.trace.setVisible(bool(plan and playback.get('valid')))
        if plan:
            self.trace_time.setText('%.2f / %.2f s' % (playback.get('elapsed', 0), plan.get('duration', 0)))
        self.trace_play.setEnabled(not playback.get('running'))
        self.trace_stop.setEnabled(bool(playback.get('running')))
        self.follow_note.setText(T('Animazione stimata dai comandi · senza feedback fisico' if s.get('follow') else 'Target virtuale · il robot non viene mosso'))
        tcp = s.get('tcp') or [0, 0, 0]
        self.tcp.setText('TCP: X %.1f · Y %.1f · Z %.1f mm' % tuple(v * 1000 for v in tcp[:3]))
        collisions = s.get('collisions') or []
        self.collisions.setVisible(bool(collisions))
        self.collisions.setText(T('Interferenza geometrica: ') + ', '.join(collisions))


class ModelHomeEditor(QDialog):
    """Align the model HOME to the real arm: model offsets only, no motor motion."""

    def __init__(self, m, window):
        super().__init__(window)
        self.m = m
        self.setWindowTitle(T('Allinea HOME del modello'))
        self.resize(980, 720)
        s = m.studio
        self.source = s['model'].get('source_hash', '')
        self.joints = movable(s)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addLayout(row(label('Allinea HOME del modello', 'title'), None, button('Annulla', None, self.reject)))
        layout.addWidget(caption('Regola i giunti finché il modello assomiglia al braccio reale nella sua HOME. Sono offset del modello a zero comandato: non muovono i motori e non misurano la calibrazione.'))
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.view = ArmView()
        self.view.setMinimumHeight(440)
        left.addWidget(self.view, 1)
        views = Segmented(VIEWS)
        views.changed.connect(self.view.set_preset)
        left.addLayout(row(button('Adatta vista', None, self.view.fit), views))
        left.addWidget(caption('Trascina: ruota · Maiusc + trascina: sposta · rotella o pizzico: zoom'))
        body.addLayout(left, 1)
        side = QVBoxLayout()
        side.setSpacing(16)
        self.texts, self.sliders = {}, {}
        for joint in self.joints:
            name = joint['name']
            text = line('HOME')
            text.textEdited.connect(lambda _t: self.changed())
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1000)
            slider.valueChanged.connect(lambda v, j=joint: self.slid(j, v))
            side.addWidget(label(name, 'section'))
            side.addLayout(row(text, label('°' if rotary(joint) else 'mm')))
            side.addWidget(slider)
            self.texts[name], self.sliders[name] = text, slider
        side.addStretch(1)
        holder = QWidget()
        holder.setLayout(side)
        holder.setFixedWidth(240)
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(260)
        body.addWidget(scroll)
        layout.addLayout(body, 1)
        self.error = label('', 'stop')
        layout.addWidget(self.error)
        self.save_button = button('Salva HOME del modello', 'prominent', self.save)
        layout.addLayout(row(button('Ripristina valori iniziali', None, self.load), None, self.save_button))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.request)
        self.offsets = {}
        m.updated.connect(self.refresh)
        self.finished.connect(self._closed)
        self.load()

    def _closed(self, _result):
        self.timer.stop()
        try:
            self.m.updated.disconnect(self.refresh)
        except (RuntimeError, TypeError):
            pass
        self.m.home_revision += 1
        self.m.home_preview = None

    def load(self):
        calibration = (self.m.studio or {}).get('calibration') or {}
        for joint in self.joints:
            value = (calibration.get(joint['name']) or {}).get('offset', 0)
            self.texts[joint['name']].setText('%.2f' % (value * multiplier(joint)))
            self._place_slider(joint, value)
        self.changed()

    def _place_slider(self, joint, value):
        low, high = joint['lower'], max(joint['upper'], joint['lower'] + 1e-6)
        slider = self.sliders[joint['name']]
        slider.blockSignals(True)
        slider.setValue(int(round((min(high, max(low, value)) - low) / (high - low) * 1000)))
        slider.blockSignals(False)

    def slid(self, joint, position):
        low, high = joint['lower'], max(joint['upper'], joint['lower'] + 1e-6)
        value = low + (high - low) * position / 1000
        self.texts[joint['name']].setText('%.2f' % (value * multiplier(joint)))
        self.changed()

    def read(self):
        values = {}
        for joint in self.joints:
            n = parse_number(self.texts[joint['name']].text())
            if n is None:
                self.error.setText(T('Completa tutti gli angoli HOME con numeri validi.'))
                return None
            value = n / multiplier(joint)
            if not joint['lower'] - 1e-8 <= value <= joint['upper'] + 1e-8:
                self.error.setText(T('Angolo HOME fuori dai limiti del giunto: ') + joint['name'])
                return None
            values[joint['name']] = value
        self.error.setText('')
        return values

    def changed(self):
        values = self.read()
        self.m.home_revision += 1
        self.m.home_preview = None
        if values is None:
            self.timer.stop()
        else:
            self.offsets = values
            for joint in self.joints:
                if not self.sliders[joint['name']].isSliderDown():
                    self._place_slider(joint, values[joint['name']])
            self.timer.start()
        self.refresh()

    def request(self):
        self.m.send('studio_home_preview', dict(offsets=self.offsets, model_hash=self.source, revision=self.m.home_revision))

    def save(self):
        values = self.read()
        if values is not None:
            self.m.send('studio_home_apply', dict(offsets=values, model_hash=self.source, confirmed=True),
                        lambda ok, _r: ok and self.accept())

    def refresh(self):
        if self.m.studio:
            self.view.update_studio(self.m.studio, self.m.state.get('grip', ''), self.m.home_preview)
        self.save_button.setEnabled(self.m.idle and self.m.home_preview is not None and not self.error.text())


class ArmJointRow(QFrame):
    def __init__(self, m, window, joint, studio):
        super().__init__()
        self.m, self.window, self.joint = m, window, joint
        self.setObjectName('Well')
        name = joint['name']
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.enabled = checkbox(name)
        self.enabled.setMinimumWidth(140)
        self.enabled.clicked.connect(self._enable)
        self.value = label('', 'mono', wrap=False)
        self.target = line('Target', 75)
        self.preview = button('Anteprima', None, self._preview)
        layout.addLayout(row(self.enabled, button('Evidenzia', None, lambda: m.send('studio_select', dict(joint=name))),
                             caption(joint.get('kind', '')), None, self.value, self.target, self.preview))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._slide)
        layout.addWidget(self.slider)
        self.motor = combo([(-1, 'Solo modello')] + [(i, 'J%d' % (i + 1)) for i in range(6)])
        self.sign = combo([(1.0, '+1'), (-1.0, '−1')])
        self.offset = line('Offset', 70)
        self.apply = button('Applica mapping', None, self._apply)
        layout.addLayout(row(label('Motore'), self.motor, label('Verso'), self.sign, caption('Offset'), self.offset,
                             caption('°' if rotary(joint) else 'mm'), self.apply, None))
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._send_slide)
        k = multiplier(joint)
        current = (studio.get('positions') or {}).get(name, 0)
        self.target.setText('%.1f' % (current * k))
        select_combo(self.motor, (studio.get('mapping') or {}).get(name, -1))
        c = (studio.get('calibration') or {}).get(name) or {}
        self.offset.setText('%.1f' % (c.get('offset', 0) * k))
        select_combo(self.sign, float(c.get('sign', 1)))

    def bounds(self):
        c = ((self.m.studio or {}).get('calibration') or {}).get(self.joint['name']) or {}
        sign, offset = c.get('sign', 1) or 1, c.get('offset', 0)
        a, b = (self.joint['lower'] - offset) / sign, (self.joint['upper'] - offset) / sign
        return min(a, b), max(min(a, b) + 1e-4, max(a, b))

    def _enable(self, value):
        m, s, name = self.m, self.m.state, self.joint['name']
        channel = ((m.studio or {}).get('mapping') or {}).get(name, -1)
        if (not value and channel >= 0 and s.get('mode') == 'robot' and s.get('connected')
                and (s.get('drive_caps') or [False] * 6)[channel] is True and (s.get('drive_state') or [None] * 6)[channel] is not False):
            m.send('axis_stop', dict(axis=channel))
            if confirm(self.window, 'Rilascia la tenuta del giunto?',
                       'Il movimento è stato fermato se il giunto era attivo. Disabilitare ENABLE toglie la corrente alle bobine: un asse sotto carico può cadere. Sostienilo prima di confermare. La sequenza verrà interrotta e HOME dovrà essere ristabilita.',
                       'Disabilita ENABLE', destructive=True):
                m.send('studio_joint', dict(joint=name, enabled=False))
        else:
            m.send('studio_joint', dict(joint=name, enabled=value))

    def _preview(self):
        v = parse_number(self.target.text())
        if v is None:
            self.m.set_message(T('Angolo non valido: completa il numero prima di applicarlo.'))
        else:
            self.m.send('studio_preview', dict(joint=self.joint['name'], value=v / multiplier(self.joint)))

    def _slide(self, position):
        low, high = self.bounds()
        self.pending = low + (high - low) * position / 1000
        if not self.timer.isActive():
            self.timer.start()

    def _send_slide(self):
        if self.pending is not None:
            self.m.send('studio_preview', dict(joint=self.joint['name'], value=self.pending))
            self.pending = None

    def _apply(self):
        o = parse_number(self.offset.text())
        if o is None:
            self.m.set_message(T('Offset non valido'))
            return
        self.m.send('studio_joint', dict(joint=self.joint['name'], axis=self.motor.currentData(), sign=self.sign.currentData(),
                                         offset=o / multiplier(self.joint)))

    def refresh(self):
        m, s, name = self.m, self.m.studio, self.joint['name']
        enabled = (s.get('enabled') or {}).get(name, True)
        mapped = (s.get('mapping') or {}).get(name, -1)
        st = m.state
        self.enabled.setChecked(enabled)
        self.enabled.setEnabled(not ((not m.idle and not enabled) or (st.get('connected') and st.get('mode') == 'robot'
                                                                        and st.get('axis_control') is not True and mapped >= 0)))
        current = (s.get('positions') or {}).get(name, 0)
        self.value.setText('%.1f %s' % (current * multiplier(self.joint), '°' if rotary(self.joint) else 'mm'))
        self.preview.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        if not self.slider.isSliderDown() and not self.timer.isActive():
            low, high = self.bounds()
            self.slider.blockSignals(True)
            self.slider.setValue(int(round((min(high, max(low, current)) - low) / (high - low) * 1000)))
            self.slider.blockSignals(False)
        self.apply.setEnabled(m.idle and not m.firmware.get('busy'))


class WorkSceneEditor(QWidget):
    """Work frames and Cartesian targets: geometry only, never a motion."""

    def __init__(self, m, window):
        super().__init__()
        self.m, self.window = m, window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(caption('Riferimenti e target sono geometrici: non avviano movimenti. Puoi modificarli da fermo senza perdere il riferimento del controllore.'))
        self.tree_box = well(QVBoxLayout())
        self.tree = self.tree_box.layout()
        self.tree.setSpacing(4)
        layout.addWidget(self.tree_box)
        layout.addWidget(caption('TCP attivo: usa il link utensile e l’offset già configurati in Giunti, mapping hardware e TCP.'))
        self.kind = Segmented([('frame', 'Riferimento di lavoro'), ('target', 'Target locale')])
        self.kind.changed.connect(lambda _v: self.refresh())
        layout.addWidget(self.kind)
        # Frame form.
        self.frame_form = QWidget()
        ff = QVBoxLayout(self.frame_form)
        ff.setContentsMargins(0, 0, 0, 0)
        self.frame_pick = combo([('', 'Nuovo riferimento')])
        self.frame_pick.activated.connect(lambda _i: self.load_frame())
        self.frame_name = line('Nome riferimento')
        self.frame_xyz, self.frame_rpy, frame_fields = self._pose_fields()
        ff.addLayout(row(label('Riferimento da modificare'), self.frame_pick, None))
        ff.addWidget(self.frame_name)
        ff.addWidget(caption('Posizione e rotazione rispetto alla base robot'))
        ff.addWidget(frame_fields)
        self.frame_save = button('Salva riferimento', 'prominent', self.save_frame)
        self.frame_delete = button('Elimina riferimento…', None, lambda: self.delete('frame', self.frame_pick.currentData()))
        ff.addLayout(row(self.frame_save, self.frame_delete, None))
        layout.addWidget(self.frame_form)
        # Target form.
        self.target_form = QWidget()
        tf = QVBoxLayout(self.target_form)
        tf.setContentsMargins(0, 0, 0, 0)
        self.target_pick = combo([('', 'Nuovo target')])
        self.target_pick.activated.connect(lambda _i: self.load_target(select=True))
        self.target_name = line('Nome target')
        self.target_frame = combo([('base', 'Base robot')])
        self.target_xyz, self.target_rpy, target_fields = self._pose_fields()
        tf.addLayout(row(label('Target da modificare'), self.target_pick, None))
        tf.addWidget(self.target_name)
        tf.addLayout(row(label('Riferimento del target'), self.target_frame, None))
        tf.addWidget(caption('Coordinate locali: cambiare riferimento conserva questi numeri e può spostare il punto nella base.'))
        tf.addWidget(target_fields)
        self.target_save = button('Salva target', 'prominent', self.save_target)
        self.target_delete = button('Elimina target…', None, lambda: self.delete('target', self.target_pick.currentData()))
        tf.addLayout(row(self.target_save, self.target_delete, None))
        layout.addWidget(self.target_form)
        self.selected = label('', 'accent')
        layout.addWidget(self.selected)
        layout.addWidget(caption('In 3D: assi X rosso, Y verde, Z blu; target selezionato arancione. Premi Adatta vista per inquadrare la scena.'))
        layout.addWidget(caption('RPY: Rz(yaw) · Ry(pitch) · Rx(roll). L’orientamento è salvato e visualizzato; l’IK attuale impone solo la posizione. Nessun MoveJ o MoveL aggiunto.'))
        self.tree_key = None
        self.model_hash = None

    def _pose_fields(self):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        xyz, rpy = [], []
        for i, name in enumerate(['X · mm', 'Y · mm', 'Z · mm']):
            grid.addWidget(caption(name), 0, i)
            xyz.append(line('0', text='0'))
            grid.addWidget(xyz[-1], 1, i)
        for i, name in enumerate(['Roll · °', 'Pitch · °', 'Yaw · °']):
            grid.addWidget(caption(name), 2, i)
            rpy.append(line('0', text='0'))
            grid.addWidget(rpy[-1], 3, i)
        return xyz, rpy, box

    def work(self):
        return (self.m.studio or {}).get('work_frames') or []

    def targets(self):
        return (self.m.studio or {}).get('cartesian_targets') or []

    def can_edit(self):
        s = self.m.studio or {}
        return (self.m.idle and not self.m.firmware.get('busy') and not s.get('program_running')
                and not (s.get('movej_preview') or {}).get('running'))

    def pose(self, xyz, rpy):
        values = [parse_number(e.text()) for e in xyz + rpy]
        if any(v is None for v in values):
            self.m.set_message(T('Completa tutte le coordinate e gli angoli con numeri validi.'))
            return None
        return dict(xyz=[v / 1000 for v in values[:3]], rpy=[v * math.pi / 180 for v in values[3:]])

    @staticmethod
    def _fill(xyz, rpy, a=None, b=None):
        for e, v in zip(xyz, a or [0, 0, 0]):
            e.setText('%.6g' % (v * 1000))
        for e, v in zip(rpy, b or [0, 0, 0]):
            e.setText('%.6g' % (v * 180 / math.pi))

    def load_frame(self):
        f = next((f for f in self.work() if f['id'] == self.frame_pick.currentData()), None)
        self.frame_name.setText(f['name'] if f else '')
        self._fill(self.frame_xyz, self.frame_rpy, f and f['xyz'], f and f['rpy'])

    def load_target(self, select=False):
        t = next((t for t in self.targets() if t['id'] == self.target_pick.currentData()), None)
        self.target_name.setText(t['name'] if t else '')
        select_combo(self.target_frame, t['frame_id'] if t else 'base')
        self._fill(self.target_xyz, self.target_rpy, t and t['xyz'], t and t['rpy'])
        if t and select:
            self.m.send('studio_target_select', dict(id=t['id']))

    def pick(self, kind, ident):
        self.kind.set_value(kind)
        if kind == 'frame':
            select_combo(self.frame_pick, ident)
            self.load_frame()
        else:
            if self.target_pick.currentData() == ident:
                self.m.send('studio_target_select', dict(id=ident))
            select_combo(self.target_pick, ident)
            self.load_target(select=True)
        self.refresh()

    def save_frame(self):
        data = self.pose(self.frame_xyz, self.frame_rpy)
        if not self.can_edit() or data is None:
            return
        name = self.frame_name.text().strip()
        data.update(id=self.frame_pick.currentData() or '', name=name)

        def done(ok, _r):
            f = next((f for f in self.work() if f['name'] == name), None)
            if ok and f:
                self.refresh()
                select_combo(self.frame_pick, f['id'])
        self.m.send('studio_frame_save', data, done)

    def save_target(self):
        data = self.pose(self.target_xyz, self.target_rpy)
        if not self.can_edit() or data is None:
            return
        name = self.target_name.text().strip()
        data.update(id=self.target_pick.currentData() or '', name=name, frame_id=self.target_frame.currentData())

        def done(ok, _r):
            t = next((t for t in self.targets() if t['name'] == name), None)
            if ok and t:
                self.refresh()
                select_combo(self.target_pick, t['id'])
        self.m.send('studio_target_save', data, done)

    def delete(self, kind, ident):
        if ident and confirm(self.window, 'Eliminare elemento della scena?',
                             'Un riferimento usato da target non può essere eliminato. L’operazione non modifica pose articolari o programmi.',
                             'Elimina', destructive=True):
            self.m.send('studio_frame_delete' if kind == 'frame' else 'studio_target_delete', dict(id=ident))

    def rebuild_tree(self):
        clear_layout(self.tree)
        selected = (self.m.studio or {}).get('selected_target')
        targets = self.targets()
        for f in self.work():
            if f['id'] == 'base':
                self.tree.addWidget(label('◎  ' + T('Base robot'), 'section'))
            else:
                b = button('▸  ' + f['name'], 'disclosure', lambda _c=False, i=f['id']: self.pick('frame', i))
                self.tree.addLayout(row(_spacer(16), b, None))
            for t in (t for t in targets if t['frame_id'] == f['id']):
                text = ('◉  ' if t['id'] == selected else '○  ') + t['name']
                b = button(text, 'disclosure', lambda _c=False, i=t['id']: self.pick('target', i))
                xyz = t.get('xyz_base') or [0, 0, 0]
                self.tree.addLayout(row(_spacer(16 if f['id'] == 'base' else 46), b, None,
                                        label('%.1f · %.1f · %.1f mm' % tuple(v * 1000 for v in xyz), 'mono')))
        if not targets:
            self.tree.addWidget(caption('Nessun target: crea un riferimento o salva un punto nella base.'))

    def refresh(self):
        s = self.m.studio or {}
        work, targets = self.work(), self.targets()
        model_hash = (s.get('model') or {}).get('source_hash')
        if model_hash != self.model_hash:
            self.model_hash = model_hash
            select_combo(self.frame_pick, '')
            select_combo(self.target_pick, '')
        set_combo_items(self.frame_pick, [('', 'Nuovo riferimento')] + [(f['id'], f['name']) for f in work if f['id'] != 'base'],
                        self.frame_pick.currentData())
        set_combo_items(self.target_pick, [('', 'Nuovo target')] + [(t['id'], t['name']) for t in targets], self.target_pick.currentData())
        set_combo_items(self.target_frame, [(f['id'], 'Base robot' if f['id'] == 'base' else f['name']) for f in work] or [('base', 'Base robot')],
                        self.target_frame.currentData())
        key = (repr(work), repr(targets), s.get('selected_target'))
        if key != self.tree_key:
            self.tree_key = key
            self.rebuild_tree()
        frame = self.kind.value == 'frame'
        self.frame_form.setVisible(frame)
        self.target_form.setVisible(not frame)
        editable = self.can_edit()
        for w in self.frame_xyz + self.frame_rpy + self.target_xyz + self.target_rpy + [self.frame_save, self.target_save, self.target_frame]:
            w.setEnabled(editable)
        self.frame_delete.setEnabled(editable and bool(self.frame_pick.currentData()))
        self.target_delete.setEnabled(editable and bool(self.target_pick.currentData()))
        t = next((t for t in targets if t['id'] == s.get('selected_target')), None)
        self.selected.setVisible(t is not None)
        if t:
            self.selected.setText(F('Target nella base: X %.2f · Y %.2f · Z %.2f mm', *[v * 1000 for v in t['xyz_base']]))


def _spacer(width):
    w = QWidget()
    w.setFixedWidth(width)
    return w


class StudioSetupPanel(Card):
    def __init__(self, m, window):
        super().__init__('Modello del braccio · URDF e calibrazione')
        self.m, self.window = m, window
        self.name = label('', 'accent', wrap=False)
        self.import_urdf = button('Importa URDF…', None, self.choose_urdf)
        self.import_eb15 = button('Importa pezzi EB-15…', None, self.choose_eb15,
                                  'Usa i file STL originali di ToolBox Robotics (EB-15 ed EBG-30) per generare il modello dettagliato solo su questo computer.')
        self.open_project = button('Apri progetto…', None, lambda: self.file_op('studio_open'))
        self.export_project = button('Esporta progetto…', None, lambda: self.file_op('studio_export'))
        self.add(row(self.name, None, self.import_urdf, self.import_eb15, self.open_project, self.export_project))
        self.status = caption()
        self.schematic = label('DOC schematico: geometria indicativa, non una calibrazione del robot fisico.', 'warning')
        self.schematic_hint = caption('Per il modello dettagliato importa gli STL originali EB-15 ed EBG-30 di ToolBox Robotics (licenza CC BY-NC-ND): restano solo su questo computer.', small=True)
        self.add(self.status, self.schematic, self.schematic_hint)
        self.joints = Disclosure('Giunti, mapping hardware e TCP')
        self.add(self.joints)
        self.joints.add(caption('Escludere un giunto blocca i comandi e le sequenze che lo richiedono. Non disabilita elettricamente il driver. Mapping, TCP e calibrazione del modello si modificano da fermo senza azzerare il controllore; richiedono una nuova verifica di corrispondenza.'))
        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(8)
        self.joints.add(self.rows_box)
        self.project_name = line('Nome progetto')
        self.default_model = button('Carica DOC 5 DOF', None, lambda: m.send('studio_default'))
        self.joints.add(row(self.project_name, button('Salva progetto', None, lambda: m.send('studio_save', dict(name=self.project_name.text()))),
                            self.default_model))
        self.tip = combo([])
        self.tool = [line('X mm', 75), line('Y mm', 75), line('Z mm', 75)]
        self.save_tcp = button('Salva TCP', None, self._save_tcp)
        self.joints.add(row(label('Link utensile'), self.tip, *self.tool, self.save_tcp, None))
        self.verified = checkbox('Ho verificato fisicamente modello, mapping, versi e offset')
        self.verified.clicked.connect(lambda v: m.send('studio_verified', dict(confirmed=v)))
        self.warnings = label('', 'warning')
        self.joints.add(self.verified, self.warnings)
        scene = Disclosure('Riferimenti di lavoro e target')
        self.scene = WorkSceneEditor(m, window)
        scene.add(self.scene)
        self.add(scene)
        env = Disclosure('Target cartesiano e ambiente di lavoro')
        self.add(env)
        env.add(caption('IK e jog sono nel pannello «IK e jog cartesiano · anteprima» dello Studio 3D.'))
        self.execute = button('Esegui target visualizzato…', 'prominent', self._execute)
        env.add(row(self.execute, None))
        env.add(caption('Ostacoli: elenco JSON con name, center [x,y,z] e size [x,y,z] in metri. Controllo conservativo dei segmenti dei link; non è una certificazione di collisione.'))
        self.obstacles = QPlainTextEdit()
        self.obstacles.setFixedHeight(100)
        env.add(self.obstacles)
        self.apply_obstacles = button('Applica ostacoli', None, self._obstacles)
        env.add(row(self.apply_obstacles, None))
        self.floor = checkbox('Piano di lavoro z = 0 (tavolo)')
        self.floor.clicked.connect(lambda v: m.send('studio_workcell', dict(floor=v)))
        self.margin = combo([(v, '%d mm' % v) for v in (0, 5, 10, 20, 30)], lambda v: m.send('studio_workcell', dict(margin=float(v))))
        self.workcell = QWidget()
        self.workcell.setLayout(column_layout(row(self.floor, None, label('Margine di sicurezza'), self.margin),
                                              caption('Geometria semplificata: capsule ricavate dalle mesh di ogni link. Controlla autocollisioni, ostacoli e tavolo; non sostituisce una verifica sul braccio.')))
        env.add(self.workcell)
        self.rows = []
        self.fields_key = None

    def can_configure(self):
        m = self.m
        return (not m.state.get('connected') and m.idle and not m.firmware.get('busy')
                and not ((m.studio or {}).get('movej_preview') or {}).get('running'))

    def choose_urdf(self):
        path, _ = QFileDialog.getOpenFileName(self.window, T('Scegli un URDF già espanso. Lascia le mesh nella cartella del pacchetto vicino al file.'),
                                              '', 'URDF (*.urdf *.xml)')
        if path:
            self.m.send('studio_import', dict(path=path))

    def choose_eb15(self):
        paths, _ = QFileDialog.getOpenFileNames(self.window, T('Scegli gli STL o gli ZIP scaricati da Thingiverse (EB-15 e EBG-30)'), '',
                                                'STL / ZIP (*.stl *.STL *.zip)')
        if paths:
            self.m.send('studio_import_eb15', dict(paths=paths))

    def file_op(self, operation):
        if operation == 'studio_open':
            path, _ = QFileDialog.getOpenFileName(self.window, T('Apri progetto…'), '', 'ZIP (*.zip)')
        else:
            path, _ = QFileDialog.getSaveFileName(self.window, T('Esporta progetto…'), 'robot-project.zip', 'ZIP (*.zip)')
        if path:
            self.m.send(operation, dict(path=path))

    def _save_tcp(self):
        values = [parse_number(e.text()) for e in self.tool]
        if any(v is None for v in values):
            self.m.set_message(T('Completa tutte le coordinate con numeri validi.'))
            return
        self.m.send('studio_tcp', dict(tip=self.tip.currentData(), tool=[v / 1000 for v in values]))

    def _execute(self):
        if confirm(self.window, 'Esegui il target visualizzato?',
                   'Il movimento usa il MoveJ condiviso: tutti i giunti insieme, con il percorso campionato contro gli ostacoli. Con firmware senza movimenti simultanei procede un giunto alla volta. Verifica calibrazione e limiti: le interferenze del modello non certificano la sicurezza fisica.',
                   'Esegui target'):
            self.m.send('studio_execute', dict(confirmed=True))

    def _obstacles(self):
        try:
            boxes = json.loads(self.obstacles.toPlainText())
        except ValueError:
            self.m.set_message(T('JSON ostacoli non valido.'))
            return
        self.m.send('studio_obstacles', dict(boxes=boxes))

    def load_fields(self, s):
        self.project_name.setText(s.get('name', ''))
        tool = s.get('tool') or [0, 0, 0]
        for e, v in zip(self.tool, tool):
            e.setText('%g' % (v * 1000))
        self.obstacles.setPlainText(json.dumps(s.get('obstacles') or [], ensure_ascii=False))

    def refresh(self):
        m, s = self.m, self.m.studio
        if not s:
            self.status.setText(T('Caricamento progetto…'))
            return
        model = s['model']
        configure = self.can_configure()
        self.name.setText(model.get('name', ''))
        for w in (self.import_urdf, self.import_eb15, self.open_project, self.default_model):
            w.setEnabled(configure)
        self.export_project.setEnabled(m.idle and not m.firmware.get('busy'))
        self.status.setText(T(s.get('status', '')))
        self.schematic.setVisible(bool(model.get('schematic')))
        self.schematic_hint.setVisible(bool(model.get('schematic')) or model.get('mesh_variant') == 'schematic')
        key = model.get('source_hash')
        if key != self.fields_key:
            self.fields_key = key
            self.load_fields(s)
            clear_layout(self.rows_box)
            self.rows = [ArmJointRow(m, self.window, j, s) for j in movable(s)]
            for r in self.rows:
                self.rows_box.addWidget(r)
        set_combo_items(self.tip, [(l['name'], l['name']) for l in model['links']], s.get('tip'))
        for r in self.rows:
            r.refresh()
        self.save_tcp.setEnabled(m.idle and not m.firmware.get('busy'))
        self.verified.setChecked(bool(s.get('verified')))
        self.verified.setEnabled(m.idle and not m.firmware.get('busy'))
        self.warnings.setText('\n'.join(T(w) for w in model.get('warnings') or []))
        self.warnings.setVisible(bool(model.get('warnings')))
        self.scene.refresh()
        self.execute.setEnabled(bool(m.state.get('home') and m.idle and not s.get('follow')))
        self.apply_obstacles.setEnabled(m.idle and not m.firmware.get('busy'))
        workcell = s.get('workcell')
        self.workcell.setVisible(workcell is not None)
        if workcell:
            self.floor.setChecked(bool(workcell.get('floor')))
            select_combo(self.margin, int(round(workcell.get('margin', 0) * 1000)))


def column_layout(*items):
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    for item in items:
        if isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    return layout


def clean(value, step=.005):
    return 0.0 if abs(value) < step else value


class CartesianPanel(Card):
    def __init__(self, m, window):
        super().__init__('IK e jog cartesiano · anteprima')
        self.m, self.window = m, window
        self.add(caption('Sposta la punta in X, Y, Z o chiedi un punto: la console calcola gli angoli dei giunti. Aggiorna solo il modello 3D, nessun comando ai motori.'))
        self.frame = combo([('base', 'Base robot'), ('tool', 'Utensile')])
        self.frame.activated.connect(lambda _i: self.refresh())
        self.add(row(label('Riferimento'), self.frame, None))
        self.readout = label('', 'mono')
        self.axis = label('', 'mono')
        self.add(row(self.readout, None, caption('Asse pinza'), self.axis))
        self.tool_note = caption('Lettura nella base robot; il jog nell’utensile segue gli assi della pinza.')
        self.singular = label('Vicino a una singolarità: alcune direzioni richiedono grandi rotazioni dei giunti.', 'warning')
        self.add(self.tool_note, self.singular, _rule())
        self.add(label('Jog cartesiano', 'headline'))
        self.step = combo([(v, '%g mm' % v) for v in (0.5, 1, 5, 10, 25)])
        select_combo(self.step, 5)
        self.keep = checkbox('Mantieni direzione utensile')
        self.keep.setChecked(True)
        self.add(row(label('Passo'), self.step, self.keep, None))
        self.jogs = []
        moves = []
        for i, name in enumerate('XYZ'):
            for sign in (-1, 1):
                b = button(('−' if sign < 0 else '+') + name, None, lambda _c=False, a=i, s=sign: self.jog(a, s))
                b.setToolTip(T('Jog meno ' if sign < 0 else 'Jog più ') + name)
                moves.append(b)
        self.jogs += moves
        self.add(row(*moves, None))
        self.turn = combo([(v, '%g°' % v) for v in (1, 5, 15)])
        select_combo(self.turn, 5)
        turns = []
        for i, name in enumerate(['Rx', 'Ry', 'Rz']):
            for sign in (-1, 1):
                b = button(('−' if sign < 0 else '+') + name, None, lambda _c=False, a=i, s=sign: self.jog(a, s, True))
                turns.append(b)
        self.jogs += turns
        self.add(row(label('Rotazione'), self.turn, *turns, None))
        self.add(caption('Le rotazioni avvengono attorno alla punta. Con cinque assi alcune inclinazioni non sono realizzabili: il passo viene rifiutato e l’anteprima resta invariata.'))
        self.add(_rule(), label('IK verso un punto', 'headline'))
        self.point = [line(n, 80, v) for n, v in zip('XYZ', ('250', '0', '100'))]
        self.orientation = combo([('free', 'Libera'), ('down', 'Verso −Z del riferimento'), ('keep', 'Mantieni attuale')])
        select_combo(self.orientation, 'down')
        self.solve = button('Calcola IK', 'prominent', self.solve_point)
        self.add(row(label('Punto · mm'), *self.point, label('Pinza'), self.orientation, self.solve, None))
        self.tool_warning = label('Per l’IK scegli la base o un riferimento di lavoro.', 'warning')
        self.add(self.tool_warning)
        self.targets_box = QWidget()
        self.target = combo([('', 'Scegli un target')])
        self.target_orientation = combo([('position', 'Solo posizione'), ('axis', 'Posizione e asse Z'), ('full', 'Asse Z e rotazione')])
        select_combo(self.target_orientation, 'axis')
        self.solve_target = button('Calcola IK sul target', None, lambda: m.send('studio_ik_target', dict(id=self.target.currentData(),
                                                                                                         orientation=self.target_orientation.currentData())))
        self.target.activated.connect(lambda _i: self.refresh())
        self.targets_box.setLayout(column_layout(row(label('Target salvato'), self.target, label('Orientamento'), self.target_orientation,
                                                     self.solve_target, None),
                                                 caption('Nei target l’asse Z è la direzione della pinza (uscente dalla flangia) e l’asse X la sua rotazione.')))
        self.add(self.targets_box)
        self.report = QVBoxLayout()
        self.report.setSpacing(6)
        self.add(self.report)
        self.add(caption('Solo anteprima: il calcolo usa le quote del modello, non misure del robot. Per muovere il braccio usa «Esegui target visualizzato…»: stesso MoveJ condiviso, con conferma.', small=True))
        self.report_key = None

    def jog(self, axis, sign, rotate=False):
        translation, rotation = [0.0] * 3, [0.0] * 3
        if rotate:
            rotation[axis] = sign * self.turn.currentData()
        else:
            translation[axis] = sign * self.step.currentData()
        self.m.send('studio_jog', dict(frame=self.frame.currentData(), translation=translation, rotation=rotation,
                                       keep_axis=self.keep.isChecked()))

    def solve_point(self):
        values = [parse_number(e.text()) for e in self.point]
        if any(v is None for v in values):
            self.m.set_message(T('Inserisci X, Y e Z in millimetri.'))
            return
        self.m.send('studio_ik', dict(target=[v / 1000 for v in values], frame=self.frame.currentData(),
                                      orientation=self.orientation.currentData()))

    @staticmethod
    def branch(s):
        parts = []
        labels = s.get('labels') or {}
        if 'reach' in labels:
            parts.append(T('Braccio in avanti' if labels['reach'] == 'front' else 'Braccio all’indietro'))
        if 'elbow' in labels:
            parts.append(T('gomito') + ' ' + labels['elbow'])
        return ' · '.join(parts)

    def rebuild_report(self, report, can):
        clear_layout(self.report)
        if not report:
            return
        self.report.addWidget(_rule())
        self.report.addWidget(label(report.get('message', ''), None if report.get('ok') else 'stop', selectable=True))
        if report.get('singular'):
            self.report.addWidget(label('Vicino a una singolarità: alcune direzioni richiedono grandi rotazioni dei giunti.', 'warning'))
        if report.get('collisions'):
            self.report.addWidget(label(T('Interferenza con gli ostacoli: ') + ', '.join(report['collisions']), 'warning'))
        for i, s in enumerate(report.get('solutions') or []):
            box = QVBoxLayout()
            box.setSpacing(3)
            box.addWidget(label(self.branch(s), 'section'))
            box.addWidget(label(' · '.join('%s %.1f°' % (j['name'], j['deg']) for j in s.get('joints', [])), 'mono'))
            details = [F('variazione massima %.1f°', s.get('change_deg', 0))]
            if s.get('axis_error_deg') is not None:
                details.append(F('scarto asse %.2f°', s['axis_error_deg']))
            if s.get('roll_error_deg') is not None:
                details.append(F('scarto rotazione %.2f°', s['roll_error_deg']))
            box.addWidget(caption(' · '.join(details)))
            if s.get('at_limit'):
                box.addWidget(label(T('Al limite: ') + ', '.join(s['at_limit']), 'warning'))
            if report.get('chosen') == i:
                action = label('In anteprima', 'accent')
            else:
                action = button('Usa', None, lambda _c=False, k=i: self.m.send('studio_ik_choose', dict(index=k)))
                action.setEnabled(can)
            self.report.addWidget(well(row(label(str(i + 1), 'small'), box, None, action), 'Well', 8))

    def refresh(self):
        m, s = self.m, self.m.studio or {}
        cart = s.get('cartesian') or {}
        readout = cart.get('readout') or {}
        frames = readout.get('frames') or []
        current = self.frame.currentData()
        set_combo_items(self.frame, [('base', 'Base robot')] + [(f['id'], f['name']) for f in frames if f['id'] != 'base'] + [('tool', 'Utensile')],
                        current if current == 'tool' or any(f['id'] == current for f in frames) else 'base')
        frame = self.frame.currentData()
        r = next((f for f in frames if f['id'] == ('base' if frame == 'tool' else frame)), None)
        if r and len(r.get('xyz', [])) == 3:
            self.readout.setText('X %.1f · Y %.1f · Z %.1f mm' % tuple(clean(v, .05) for v in r['xyz']))
            self.axis.setText('%.2f · %.2f · %.2f' % tuple(clean(v) for v in r['axis']))
        self.tool_note.setVisible(frame == 'tool')
        self.singular.setVisible(bool(readout.get('singular')))
        can = ready(m) and not (s.get('movej_preview') or {}).get('running')
        for b in self.jogs:
            b.setEnabled(can)
        self.solve.setEnabled(can and frame != 'tool')
        self.tool_warning.setVisible(frame == 'tool')
        targets = s.get('cartesian_targets') or []
        self.targets_box.setVisible(bool(targets))
        set_combo_items(self.target, [('', 'Scegli un target')] + [(t['id'], t['name']) for t in targets], self.target.currentData())
        self.solve_target.setEnabled(can and bool(self.target.currentData()))
        report = cart.get('report')
        key = (repr(report), can)
        if key != self.report_key:
            self.report_key = key
            self.rebuild_report(report, can)


def _rule():
    r = QFrame()
    r.setObjectName('CardRule')
    r.setFixedHeight(1)
    return r


class MoveJPreviewPanel(Card):
    def __init__(self, m, window):
        super().__init__('MoveJ · anteprima del percorso')
        self.m, self.window = m, window
        self.add(caption('Pianifica un movimento articolare simultaneo, osserva il TCP in 3D, poi eseguilo con lo stesso piano. Le velocità sono quelle di Muovi e osserva.'))
        self.source = Segmented([('joints', 'Angoli assoluti'), ('studio', 'Giunti Studio'), ('pose', 'Posa salvata'),
                                 ('program', 'Programma'), ('movel', 'Retta MoveL')])
        self.source.changed.connect(lambda _v: (self.discard(), self.refresh()))
        self.add(self.source)
        # Absolute angles.
        self.joints_box = QWidget()
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        self.angles = []
        for i in range(6):
            e = line('0', text='0')
            e.textEdited.connect(lambda _t: self.discard())
            grid.addLayout(row(label('J%d · °' % (i + 1), 'mono'), e), i // 3, i % 3)
            self.angles.append(e)
        self.joints_box.setLayout(column_layout(grid, row(button('Usa angoli attuali', None, self.use_current), None)))
        self.add(self.joints_box)
        # MoveL.
        self.line_box = QWidget()
        self.line_frame = combo([('base', 'Base robot')])
        self.line_frame.activated.connect(lambda _i: self.discard())
        self.line_point = [line(n, 80, v) for n, v in zip('XYZ', ('250', '50', '100'))]
        for e in self.line_point:
            e.textEdited.connect(lambda _t: self.discard())
        self.line_orientation = combo([('keep', 'Mantieni'), ('free', 'Libera')], lambda _v: self.discard())
        self.tolerance = combo([(v, '%g mm' % v) for v in (0.1, 0.2, 0.5, 1, 2)], lambda _v: self.discard())
        select_combo(self.tolerance, 0.5)
        self.line_target = combo([('', 'Scegli un target')], self.use_target)
        self.line_target_row = QWidget()
        self.line_target_row.setLayout(row(label('Usa target salvato'), self.line_target, None))
        self.line_box.setLayout(column_layout(
            caption('La punta va in linea retta dalla posizione comandata al punto scelto. Il percorso è diviso nei movimenti simultanei necessari per restare entro la tolleranza; tra un tratto e l’altro il braccio si ferma brevemente.'),
            row(label('Riferimento'), self.line_frame, label('Arrivo · mm'), *self.line_point, None),
            row(label('Pinza'), self.line_orientation, label('Tolleranza'), self.tolerance, button('Usa punto attuale', None, self.use_point), None),
            self.line_target_row))
        self.add(self.line_box)
        self.pose = combo([])
        self.pose.activated.connect(lambda _i: self.discard())
        self.pose_box = QWidget()
        self.pose_box.setLayout(row(label('Posa da pianificare'), self.pose, None))
        self.add(self.pose_box)
        self.return_start = checkbox('Includi ritorno al punto iniziale', lambda _v: self.discard())
        self.add(self.return_start)
        self.plan_button = button('Pianifica MoveJ', None, self.prepare)
        self.clear_button = button('Cancella piano', None, lambda: m.send('studio_movej_clear'))
        self.execute = button('Esegui MoveJ…', 'prominent', self.confirm_execute)
        self.stop = button('STOP', 'danger', lambda: m.send('stop'))
        self.add(row(self.plan_button, self.clear_button, None, self.execute, self.stop))
        self.wait_note = label('Attendi il controllore fermo per pianificare o eseguire MoveJ.', 'warning')
        self.home_note = label('Conferma HOME per eseguire il piano; l’anteprima resta disponibile.', 'warning')
        self.exec_label = label('', 'headline')
        self.done_label = label('', 'accent')
        self.exec_error = label('', 'stop', selectable=True)
        self.speed_note = label('Applica le velocità modificate prima di pianificare.', 'warning')
        self.movel_info = label('', 'section')
        self.movel_axis = caption()
        self.measured = label('', 'mono')
        self.add(self.wait_note, self.home_note, self.exec_label, self.done_label, self.exec_error, self.speed_note, self.movel_info,
                 self.movel_axis, self.measured)
        self.plan_box = QWidget()
        pb = QVBoxLayout(self.plan_box)
        pb.setContentsMargins(0, 0, 0, 0)
        self.duration = label('', 'mono')
        self.samples = caption()
        self.slider = TimeSlider(m)
        self.play = button('Riproduci anteprima', None, lambda: m.send('studio_movej_play', dict(id=self.slider.plan_id)))
        self.stop_preview = button('Arresta anteprima', 'danger', lambda: m.send('studio_movej_stop'))
        self.clock = label('', 'mono')
        self.stages = QVBoxLayout()
        self.stages.setSpacing(6)
        pb.addWidget(_rule())
        pb.addLayout(row(self.duration, None, self.samples))
        pb.addWidget(self.slider)
        pb.addLayout(row(self.play, self.stop_preview, None, self.clock))
        pb.addLayout(self.stages)
        self.add(self.plan_box)
        self.error = label('', 'stop', selectable=True)
        self.add(self.error)
        self.add(caption('Partenza dagli angoli del controllore. Traccia campionata: non verifica collisioni complete delle mesh. Le sequenze collegano direttamente le pose abilitate, senza ripercorrere la cronologia.', small=True))
        self.stages_key = None

    def playback(self):
        return (self.m.studio or {}).get('movej_preview') or {}

    def discard(self):
        if self.playback().get('plan'):
            self.m.send('studio_movej_clear')

    def use_current(self):
        for e, v in zip(self.angles, self.m.state['pos']):
            e.setText('%.2f' % v)
        self.discard()

    def use_point(self):
        frames = (((self.m.studio or {}).get('cartesian') or {}).get('readout') or {}).get('frames') or []
        r = next((f for f in frames if f['id'] == self.line_frame.currentData()), None)
        if r and len(r.get('xyz', [])) == 3:
            for e, v in zip(self.line_point, r['xyz']):
                e.setText('%.1f' % v)
            self.discard()

    def use_target(self, ident):
        t = next((t for t in (self.m.studio or {}).get('cartesian_targets') or [] if t['id'] == ident), None)
        if t:
            select_combo(self.line_frame, t['frame_id'])
            for e, v in zip(self.line_point, t['xyz']):
                e.setText('%.1f' % (v * 1000))
            self.discard()

    def prepare(self):
        source = self.source.value
        request = dict(source=source, return_to_start=self.return_start.isChecked())
        if source == 'joints':
            numbers = [parse_number(e.text()) for e in self.angles]
            if any(v is None for v in numbers):
                self.m.set_message(T('Inserisci sei angoli validi in gradi.'))
                return
            request['targets'] = numbers
        elif source == 'pose':
            request['index'] = self.pose.currentData() or 0
        elif source == 'movel':
            values = [parse_number(e.text()) for e in self.line_point]
            if any(v is None for v in values):
                self.m.set_message(T('Inserisci X, Y e Z in millimetri.'))
                return
            request.update(target=[v / 1000 for v in values], frame=self.line_frame.currentData(),
                           orientation=self.line_orientation.currentData(), tolerance=self.tolerance.currentData())
        self.m.send('studio_movej_plan', request)

    def confirm_execute(self):
        plan = self.playback().get('plan')
        if not plan:
            return
        demo = self.m.state.get('mode') == 'demo'
        text = F('Anteprima: %lld tratti, durata stimata %.1f s. Esecuzione con il controllore simulato.' if demo else
                 'ROBOT REALE: %lld tratti, durata stimata %.1f s. Il braccio si muove con movimenti simultanei, uno per tratto, e attende il DONE della Mega. Tieni pronto lo STOP.',
                 len(plan.get('stages', [])), plan.get('duration', 0))
        if confirm(self.window, 'Eseguire il piano MoveJ?', text, 'Esegui MoveJ'):
            self.m.send('studio_movej_execute', dict(id=plan['id'], confirmed=True))

    def rebuild_stages(self, plan, playback, executing):
        clear_layout(self.stages)
        for i, stage in enumerate(plan.get('stages', [])):
            box = QVBoxLayout()
            box.setSpacing(2)
            box.addWidget(label(stage.get('name', ''), 'section'))
            box.addWidget(label('%.2f–%.2f s' % (stage.get('start_time', 0), stage.get('end_time', 0)), 'mono'))
            axes, peaks = stage.get('axes') or [], stage.get('peaks') or []
            if axes and peaks:
                box.addWidget(label(' · '.join('J%d %.2f °/s' % (a + 1, peaks[a]) for a in axes if a < len(peaks)), 'mono'))
            mark = ''
            if executing and playback.get('exec_stage') == i:
                mark = '⚡'
            elif playback.get('running') and playback.get('stage') == i:
                mark = '▶'
            self.stages.addWidget(well(row(label(str(i + 1), 'small'), box, None, label(mark, 'accent')), 'Well', 6))

    def refresh(self):
        m, s = self.m, self.m.studio or {}
        playback = self.playback()
        plan = playback.get('plan')
        executing = bool(playback.get('executing'))
        running = bool(playback.get('running'))
        can = ready(m) and not executing
        source = self.source.value
        self.source.setEnabled(not running)
        self.joints_box.setVisible(source == 'joints')
        self.line_box.setVisible(source == 'movel')
        self.pose_box.setVisible(source == 'pose')
        for w in (self.joints_box, self.line_box, self.pose_box, self.return_start):
            w.setEnabled(not running)
        work = s.get('work_frames') or []
        set_combo_items(self.line_frame, [('base', 'Base robot')] + [(f['id'], f['name']) for f in work if f['id'] != 'base'],
                        self.line_frame.currentData())
        targets = s.get('cartesian_targets') or []
        self.line_target_row.setVisible(bool(targets))
        set_combo_items(self.line_target, [('', 'Scegli un target')] + [(t['id'], t['name']) for t in targets], self.line_target.currentData())
        set_combo_items(self.pose, [(i, '%d · %s' % (i + 1, p.get('name', ''))) for i, p in enumerate(m.state['sequence'])], self.pose.currentData())
        self.plan_button.setEnabled(can and not running and not m.speed_edits)
        self.clear_button.setVisible(plan is not None)
        self.execute.setEnabled(bool(can and m.state.get('home') and playback.get('valid') and not running and not m.speed_edits))
        self.stop.setVisible(executing)
        self.wait_note.setVisible(not can and not executing)
        self.home_note.setVisible(bool(plan and not m.state.get('home') and not executing))
        self.exec_label.setVisible(bool(executing and plan))
        if executing and plan:
            count = len(plan.get('stages', []))
            self.exec_label.setText(F('Esecuzione MoveJ · tratto %lld di %lld', min(max(playback.get('exec_stage') or 0, 0) + 1, count), count))
            set_role(self.exec_label, 'accent')
        self.done_label.setVisible(bool(playback.get('exec_done')))
        self.done_label.setText(T('MoveJ eseguito in Anteprima.' if m.state.get('mode') == 'demo' else
                                  'MoveJ eseguito: DONE dalla Mega per ogni gruppo; posizione non misurata.'))
        error = playback.get('exec_error') or ''
        self.exec_error.setVisible(bool(error))
        if error:
            self.exec_error.setText(T('MoveJ interrotto: ') + T(error) + (' ' if error.endswith('.') else '. ') +
                                    T('Nessuna ripresa automatica: verifica il braccio e ristabilisci HOME.'))
        self.speed_note.setVisible(bool(m.speed_edits))
        movel = (plan or {}).get('movel')
        self.movel_info.setVisible(bool(movel))
        self.movel_axis.setVisible(bool(movel))
        if movel:
            self.movel_info.setText(F('Retta di %.1f mm · %lld tratti · deviazione massima %.2f mm (tolleranza %.2f mm) · arrivo entro %.2f mm',
                                      movel['length_mm'], movel['segments'], movel['max_deviation_mm'], movel['tolerance_mm'], movel['end_error_mm']))
            if movel.get('axis_error_deg') is not None:
                self.movel_axis.setText(F('Orientamento mantenuto: scarto asse massimo %.2f°, rotazione %.2f°', movel['axis_error_deg'],
                                          movel.get('roll_error_deg') or 0))
            else:
                self.movel_axis.setText(T('Orientamento libero: la pinza ruota come serve per seguire la retta.'))
        measured = playback.get('exec_measured') or []
        self.measured.setVisible(bool(measured and not executing))
        if measured:
            moves = [x for x in measured if x['kind'] == 'movej']
            self.measured.setText(F('Durata misurata %.2f s · stimata %.2f s · scarto medio per tratto %.2f s', sum(x['actual'] for x in measured),
                                    sum(x['planned'] for x in measured),
                                    sum(x['actual'] - x['planned'] for x in moves) / len(moves) if moves else 0))
        self.plan_box.setVisible(plan is not None)
        if plan:
            self.duration.setText(F('Durata stimata: %.2f s', plan.get('duration', 0)))
            self.samples.setText(F('%lld campioni · passo massimo 1°', plan.get('sample_count', 0)))
            self.slider.show_plan(plan, playback)
            self.play.setEnabled(can and bool(playback.get('valid')) and not running)
            self.stop_preview.setEnabled(running)
            self.clock.setText('%.2f / %.2f s' % (self.slider.seconds() if self.slider.isSliderDown() else playback.get('elapsed', 0), plan.get('duration', 0)))
            key = (plan.get('id'), playback.get('stage'), playback.get('exec_stage'), running, executing)
            if key != self.stages_key:
                self.stages_key = key
                self.rebuild_stages(plan, playback, executing)
        self.error.setVisible(bool(playback.get('error')))
        self.error.setText(T(playback.get('error') or ''))


# --- Offline programs ---------------------------------------------------------------------------

OPENS = ('loop', 'if', 'function')
KINDS = [('movej', 'MoveJ'), ('movel', 'MoveL'), ('grip', 'Pinza'), ('wait', 'Attesa'), ('pose', 'Posa registrata'),
         ('sensor', 'Attesa sensore'), ('output', 'Uscita digitale'), ('loop', 'Ripeti N volte'), ('if', 'Se (condizione)'),
         ('set', 'Variabile'), ('function', 'Funzione'), ('call', 'Richiama funzione'), ('return', 'Restituisci'), ('note', 'Nota')]
ICONS = {'movej': '↗', 'movel': '╲', 'pose': '☺', 'grip': '✋', 'wait': '⏱', 'sensor': '◉', 'output': '⏻', 'function': '{ }',
         'call': '↳', 'repeat': '↻', 'note': '✎', 'loop': '↻', 'if': '⑂', 'else': '↪', 'end': '↲', 'set': '𝑥', 'return': '↩'}
MOTION_KINDS = ('movej', 'movel', 'loop', 'if', 'set', 'output', 'function', 'call', 'return')


def depths(blocks):
    level, result = 0, []
    for b in blocks:
        if b['kind'] in ('end', 'else'):
            level = max(0, level - 1)
        result.append(level)
        if b['kind'] in OPENS or b['kind'] == 'else':
            level += 1
    return result


def markers(blocks, index):
    level, result = 0, []
    for i in range(index + 1, len(blocks)):
        kind = blocks[i]['kind']
        if kind in OPENS:
            level += 1
        elif kind == 'else' and level == 0:
            result.append(i)
        elif kind == 'end':
            if level == 0:
                result.append(i)
                break
            level -= 1
    return result


class ProgramPanel(Card):
    def __init__(self, m, window):
        super().__init__('Programmi · istruzioni e anteprima')
        self.m, self.window = m, window
        self.selected = None
        self.editing = None
        self.scenario = {}
        self.title = label('', 'headline')
        self.running = caption()
        self.add(row(self.title, None, self.running))
        self.intro = caption()
        self.add(self.intro)
        self._build_editor()
        self.empty = caption('Nessuna istruzione. Esempio di presa: MoveJ sopra il pezzo, MoveL giù, chiudi la pinza, MoveL su, MoveJ sopra il deposito, MoveL giù, apri, MoveL su.')
        self.add(self.empty)
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        self.add(self.list)
        self._build_plan()
        # Pose-only programs.
        self.simple = QWidget()
        self.run_simple = button('Esegui programma…', 'prominent', self.confirm_simple)
        self.cancel_simple = button('Interrompi programma', None, lambda: m.send('studio_cancel'))
        self.simple_error = label('', 'stop')
        self.simple.setLayout(column_layout(row(self.run_simple, self.cancel_simple, None), self.simple_error))
        self.add(self.simple, _rule())
        self.validation = ValidationView(m)
        self.add(self.validation)
        editor = Disclosure('Editor delle istruzioni JSON')
        self.json = QPlainTextEdit()
        self.json.setFixedHeight(180)
        font = self.json.font()
        font.setFamilies(['Menlo', 'Consolas', 'DejaVu Sans Mono', 'monospace'])
        self.json.setFont(font)
        self.json_buttons = QWidget()
        self.json_buttons.setLayout(row(button('Rileggi istruzioni', None, self.read_json), button('Valida e salva istruzioni', None, self.save_json), None))
        editor.add(self.json, self.json_buttons)
        self.add(editor)
        self.add(caption('Il programma è salvato nel progetto a ogni modifica. Le istruzioni posa collegano direttamente le destinazioni salvate e includono pausa e comando pinza.', small=True))
        self.pose_preview = QWidget()
        self.preview_pose = combo([])
        self.fraction = QSlider(Qt.Horizontal)
        self.fraction.setRange(0, 100)
        self.fraction_label = label('0%', 'mono')
        self.fraction.valueChanged.connect(self._fraction)
        self.pose_preview.setLayout(row(label('Anteprima pose'), self.preview_pose, self.fraction, self.fraction_label))
        self.add(self.pose_preview)
        self.list_key = None

    # Editor ---------------------------------------------------------------------------------------
    def _build_editor(self):
        box = QVBoxLayout()
        box.setSpacing(8)
        self.kind = combo(KINDS, lambda _v: self.refresh())
        self.name = line('Nome (facoltativo)')
        self.name.setMaximumWidth(220)
        self.add_button = button('＋ Aggiungi istruzione', 'prominent', self.add_block)
        box.addLayout(row(label('Istruzione'), self.kind, self.name, None, self.add_button))
        self.cancel_edit = button('Annulla modifica', None, self.stop_editing)
        box.addLayout(row(self.cancel_edit, None))
        self.options = {}

        def option(kind, *items):
            w = QWidget()
            w.setLayout(row(*items, None))
            self.options[kind] = w
            box.addWidget(w)
        self.destination = combo([('target', 'Target della scena'), ('home', 'HOME'), ('pose', 'Posa salvata'), ('joints', 'Angoli attuali')],
                                 lambda _v: self.refresh())
        self.target = combo([('', 'Scegli')])
        self.target_l = combo([('', 'Scegli')])
        self.above = line('0', 60, '60')
        self.above_l = line('0', 60, '60')
        self.pose = combo([])
        self.pose2 = combo([])
        self.movej_target = QWidget()
        self.movej_target.setLayout(row(label('Target'), self.target, label('Z sopra · mm'), self.above))
        self.movej_pose = QWidget()
        self.movej_pose.setLayout(row(label('Posa'), self.pose))
        option('movej', label('Verso'), self.destination, self.movej_target, self.movej_pose)
        option('movel', label('Target'), self.target_l, label('Z sopra · mm'), self.above_l)
        option('pose', label('Posa'), self.pose2)
        self.grip = Segmented([('chiudi', 'Chiudi'), ('apri', 'Apri')])
        option('grip', label('Pinza'), self.grip)
        self.seconds = line('1', 70, '1')
        option('wait', label('Secondi'), self.seconds)
        self.sensor = line('Nome sensore', 160)
        self.expected = line('Valore', 60, '1')
        self.sensor_timeout = line('10', 60, '10')
        option('sensor', self.sensor, self.expected, label('Timeout s'), self.sensor_timeout)
        self.output = combo([('', 'Scegli uscita')])
        self.output_value = checkbox('Valore 1')
        self.output_value.setChecked(True)
        self.output_timeout = line('10', 60, '10')
        option('output', label('Uscita digitale'), self.output, self.output_value, label('Timeout s'), self.output_timeout)
        self.function_name = line('Nome funzione, es. prendi', 200)
        self.parameters = line('Parametri separati da virgole')
        option('function', self.function_name, self.parameters)
        self.called = combo([('', 'Scegli funzione')], lambda _v: self.rebuild_arguments())
        self.result_variable = line('Variabile risultato (facoltativa)', 210)
        option('call', label('Funzione'), self.called, self.result_variable)
        self.return_value = line('Espressione restituita (facoltativa)')
        option('return', self.return_value)
        self.times = line('3', 90, '3')
        self.loop_variable = line('facoltativo, es. strato', 170)
        option('loop', label('Volte'), self.times, label('Contatore'), self.loop_variable)
        self.condition = line('es. presente == 1')
        self.with_else = checkbox('con Altrimenti')
        option('if', label('Condizione'), self.condition, self.with_else)
        self.variable = line('nome, es. passo', 150)
        self.value = line('0', None, '0')
        option('set', self.variable, label('='), self.value)
        self.note = line('Testo della nota')
        option('note', self.note)
        self.arguments_box = QGridLayout()
        self.argument_edits = {}
        box.addLayout(self.arguments_box)
        self.function_hint = caption('Definisci la funzione una volta, seleziona il suo inizio e aggiungi il corpo. Richiamala passando i parametri; le variabili sono locali. Restituisci è facoltativo. Le nuove definizioni sono aggiunte in fondo, al livello principale.', small=True)
        box.addWidget(self.function_hint)
        self.orientation = combo([('axis', 'Asse del target'), ('position', 'Solo posizione')])
        self.line_orientation = combo([('keep', 'Mantieni'), ('free', 'Libera')])
        self.tolerance = combo([(v, '%g mm' % v) for v in (0.1, 0.2, 0.5, 1, 2)])
        select_combo(self.tolerance, 0.5)
        self.speed = combo([(float(v), '%d%%' % v) for v in range(10, 101, 10)])
        select_combo(self.speed, 100.0)
        self.speed.setToolTip(T('Percentuale delle velocità dei giunti di Muovi e osserva; minimo 1 °/s per asse.'))
        self.orientation_row = QWidget()
        self.orientation_box = QWidget()
        self.orientation_box.setLayout(row(label('Pinza'), self.orientation))
        self.line_box = QWidget()
        self.line_box.setLayout(row(label('Pinza'), self.line_orientation, label('Tolleranza'), self.tolerance))
        self.orientation_row.setLayout(row(self.orientation_box, self.line_box, label('Velocità'), self.speed, None))
        box.addWidget(self.orientation_row)
        self.insert_hint = caption(small=True)
        self.expr_hint = caption('Espressioni: numeri, variabili, sensori (solo nelle condizioni), operazioni + - * /, confronti == != < <= > >=, and or not. Le quote «Z sopra» accettano anche espressioni come 60 + strato*20.', small=True)
        self.target_hint = label('Crea prima i target nella scena di lavoro (pannello Target cartesiani): punto e orientamento della pinza.', 'warning')
        box.addWidget(self.insert_hint)
        box.addWidget(self.expr_hint)
        box.addWidget(self.target_hint)
        self.editor = well(box, 'Well', 10)
        self.add(self.editor)

    def rebuild_arguments(self):
        clear_layout(self.arguments_box)
        drafts = {k: e.text() for k, e in self.argument_edits.items()}
        self.argument_edits = {}
        definition = self.chosen_function()
        if self.kind.currentData() != 'call' or not definition:
            return
        for i, parameter in enumerate(definition.get('parameters') or []):
            e = line('Valore o espressione', text=drafts.get(parameter, ''))
            self.argument_edits[parameter] = e
            self.arguments_box.addLayout(row(caption(parameter), e), i // 3, i % 3)

    def blocks(self):
        return list((self.m.studio or {}).get('blocks') or [])

    def functions(self):
        return [b for b in self.blocks() if b['kind'] == 'function']

    def chosen_function(self):
        return next((f for f in self.functions() if f.get('function') == self.called.currentData()), None)

    def targets(self):
        return (self.m.studio or {}).get('cartesian_targets') or []

    def save_blocks(self, blocks):
        self.m.send('studio_blocks', dict(blocks=blocks))

    def add_block(self):
        kind = self.kind.currentData()
        seq = self.m.state['sequence']
        b = dict(kind=kind, name='', enabled=True)
        destination = self.destination.currentData()
        above = (self.above if kind == 'movej' else self.above_l).text().strip()
        target_combo = self.target if kind == 'movej' else self.target_l
        if (kind == 'movej' and destination == 'target') or kind == 'movel':
            if not above:
                self.m.set_message(T('Completa la quota Z prima di aggiungere il movimento.'))
                return
        z = parse_number(above)
        expression = z is None and bool(above)
        z = z or 0.0
        z_expression = ['', '', above] if expression else None
        target_id = target_combo.currentData()
        target_name = next((t['name'] for t in self.targets() if t['id'] == target_id), '')
        height = (' Z ' + above) if expression else ('' if z == 0 else ' %+.0f mm' % z)
        speed = self.speed.currentData()
        if kind == 'movej':
            b.update(to=destination, speed=speed)
            if destination == 'target':
                if not target_id:
                    self.m.set_message(T('Scegli un target della scena.'))
                    return
                b.update(target=target_id, offset=[0, 0, z], orientation=self.orientation.currentData(), name='MoveJ → ' + target_name + height)
                if z_expression:
                    b['offset_expr'] = z_expression
            elif destination == 'pose':
                index = self.pose.currentData() or 0
                b.update(index=index, name='MoveJ → ' + (seq[index]['name'] if index < len(seq) else 'posa'))
            elif destination == 'joints':
                pos = self.m.state['pos']
                b.update(angles=pos, name='MoveJ → ' + ' '.join('%.0f°' % v for v in pos[:5]))
            else:
                b['name'] = 'MoveJ → HOME'
        elif kind == 'movel':
            if not target_id:
                self.m.set_message(T('Scegli un target della scena.'))
                return
            b.update(to='target', target=target_id, offset=[0, 0, z], orientation=self.line_orientation.currentData(),
                     tolerance=self.tolerance.currentData(), speed=speed, name='MoveL → ' + target_name + height)
            if z_expression:
                b['offset_expr'] = z_expression
        elif kind == 'pose':
            index = self.pose2.currentData() or 0
            b.update(index=index, name=seq[index]['name'] if index < len(seq) else 'Posa %d' % (index + 1))
        elif kind == 'grip':
            b.update(command=self.grip.value, name='Chiudi pinza' if self.grip.value == 'chiudi' else 'Apri pinza')
        elif kind == 'wait':
            n = parse_number(self.seconds.text())
            if n is None:
                self.m.set_message(T('Secondi non validi.'))
                return
            b.update(seconds=n, name='Attendi %s s' % self.seconds.text())
        elif kind == 'sensor':
            n, t = parse_number(self.expected.text()), parse_number(self.sensor_timeout.text())
            if n is None or t is None:
                self.m.set_message(T('Completa valore e timeout del sensore con numeri validi.'))
                return
            b.update(sensor=self.sensor.text(), expected=n, timeout=t, name='Attendi ' + self.sensor.text())
        elif kind == 'output':
            timeout = parse_number(self.output_timeout.text())
            if not self.output.currentData() or timeout is None:
                self.m.set_message(T('Scegli un’uscita e un timeout valido.'))
                return
            b.update(output=self.output.currentData(), output_value=self.output_value.isChecked(), timeout=timeout,
                     name=T('Uscita') + ' ' + self.output.currentData() + ' = ' + ('1' if self.output_value.isChecked() else '0'))
        elif kind == 'function':
            name = self.function_name.text().strip()
            text = self.parameters.text().strip()
            b.update(function=name, parameters=[p.strip() for p in text.split(',')] if text else [], name=T('Funzione') + ' ' + name)
        elif kind == 'call':
            definition = self.chosen_function()
            if not definition:
                self.m.set_message(T('Scegli una funzione definita nel progetto.'))
                return
            b.update(function=self.called.currentData(),
                     arguments={p: (self.argument_edits[p].text() if p in self.argument_edits else '') for p in definition.get('parameters') or []},
                     name=T('Richiama') + ' ' + self.called.currentData())
            if self.result_variable.text().strip():
                b['result'] = self.result_variable.text().strip()
        elif kind == 'return':
            value = self.return_value.text().strip()
            b.update(value=value, name=T('Restituisci') + (' ' + value if value else ''))
        elif kind == 'loop':
            b.update(times=self.times.text(), name='Ripeti ' + self.times.text() + ' volte')
            if self.loop_variable.text():
                b['variable'] = self.loop_variable.text()
        elif kind == 'if':
            if not self.condition.text():
                self.m.set_message(T('Scrivi la condizione, per esempio presente == 1.'))
                return
            b.update(condition=self.condition.text(), name='Se ' + self.condition.text())
        elif kind == 'set':
            if not self.variable.text():
                self.m.set_message(T('Scrivi il nome della variabile.'))
                return
            b.update(variable=self.variable.text(), value=self.value.text(), name=self.variable.text() + ' = ' + self.value.text())
        else:
            b['name'] = self.note.text() or 'Nota'
        if self.name.text().strip():
            b['name'] = self.name.text()
        blocks = self.blocks()
        if self.editing is not None and self.editing < len(blocks):
            previous = blocks[self.editing]
            blocks[self.editing] = b
            if previous['kind'] == 'function' and previous.get('function') != b.get('function'):
                for other in blocks:
                    if other['kind'] == 'call' and other.get('function') == previous.get('function'):
                        other['function'] = b.get('function')
            self.save_blocks(blocks)
            self.selected = self.editing
            self.stop_editing()
            return
        at = len(blocks) if kind == 'function' else min((self.selected if self.selected is not None else len(blocks) - 1) + 1, len(blocks))
        added = [b]
        if kind in OPENS:
            if kind == 'if' and self.with_else.isChecked():
                added.append(dict(kind='else', name='Altrimenti', enabled=True))
            added.append(dict(kind='end', name=T('Fine funzione') if kind == 'function' else ('Fine ripeti' if kind == 'loop' else 'Fine se'), enabled=True))
        blocks[at:at] = added
        self.save_blocks(blocks)
        self.name.setText('')
        self.selected = at

    def stop_editing(self):
        self.editing = None
        self.name.setText('')
        self.list_key = None
        self.refresh()

    def edit(self, b, index):
        self.editing = self.selected = index
        select_combo(self.kind, b['kind'])
        self.name.setText(b.get('name', ''))
        if b['kind'] == 'function':
            self.function_name.setText(b.get('function', ''))
            self.parameters.setText(', '.join(b.get('parameters') or []))
        else:
            select_combo(self.called, b.get('function', ''))
            self.rebuild_arguments()
            for k, v in (b.get('arguments') or {}).items():
                if k in self.argument_edits:
                    self.argument_edits[k].setText(v)
            self.result_variable.setText(b.get('result') or '')
        self.list_key = None
        self.refresh()

    def remove(self, i):
        blocks = self.blocks()
        if blocks[i]['kind'] == 'function':
            end = markers(blocks, i)
            if end:
                del blocks[i:end[-1] + 1]
                self.save_blocks(blocks)
                self.selected = self.editing = None
                return
        indices = sorted([i] + (markers(blocks, i) if blocks[i]['kind'] in OPENS else []), reverse=True)
        for k in indices:
            del blocks[k]
        self.save_blocks(blocks)
        self.selected = None

    def swap(self, i, j):
        blocks = self.blocks()
        blocks[i], blocks[j] = blocks[j], blocks[i]
        self.save_blocks(blocks)

    def set_field(self, i, key, value):
        blocks = self.blocks()
        blocks[i][key] = value
        self.save_blocks(blocks)

    def select(self, i):
        self.selected = None if self.selected == i else i
        self.list_key = None
        self.refresh()

    # Descriptions ----------------------------------------------------------------------------------
    def offset_text(self, b):
        o, e = b.get('offset') or [0, 0, 0], b.get('offset_expr') or ['', '', '']
        parts = []
        for k, axis in enumerate('XYZ'):
            if k < len(e) and e[k]:
                parts.append(axis + ' = ' + e[k] + ' mm')
            elif k < len(o) and o[k]:
                parts.append('%s %+.0f mm' % (axis, o[k]))
        return ' '.join(parts) or None

    def detail(self, b, motion):
        pace = '%.0f%% ' % (b.get('speed') or 100) + T('velocità')
        target = next((T('target') + ' ' + t['name'] for t in self.targets() if t['id'] == b.get('target')), T('target mancante'))
        kind = b['kind']
        if kind == 'movej':
            to = b.get('to') or ''
            if to == 'target':
                return ' · '.join(x for x in [target, self.offset_text(b), T('solo posizione') if b.get('orientation') == 'position' else T('asse del target'), pace] if x)
            if to == 'pose':
                return T('angoli della posa') + ' · ' + pace
            if to == 'joints':
                return ' '.join('J%d %.1f°' % (i + 1, v) for i, v in enumerate((b.get('angles') or [])[:6])) + ' · ' + pace
            return T('tutti i giunti a 0°') + ' · ' + pace
        if kind == 'movel':
            return ' · '.join(x for x in [T('linea retta'), target, self.offset_text(b), T('pinza libera') if b.get('orientation') == 'free' else T('pinza mantenuta'),
                                          '± %.2g mm' % (b.get('tolerance') or .5), pace] if x)
        if kind == 'pose':
            return T('MoveJ agli angoli della posa') if motion else T('percorso insegnato')
        if kind == 'grip':
            return T('chiude · 1,5 s') if b.get('command') == 'chiudi' else T('apre · 1,5 s')
        if kind == 'wait':
            return '%.1f s' % (b.get('seconds') or 0)
        if kind == 'sensor':
            return F('attende %@ = %@, al massimo %@ s', b.get('sensor', ''), '%g' % (b.get('expected', 1) or 0), '%g' % (b.get('timeout') or 10))
        if kind == 'output':
            return F('%@ = %@ · conferma entro %@ s', b.get('output', ''), '1' if b.get('output_value') else '0', '%g' % (b.get('timeout') or 10))
        if kind == 'function':
            return (b.get('function') or '') + '(' + ', '.join(b.get('parameters') or []) + ') · ' + T('corpo eseguito solo dai richiami')
        if kind == 'call':
            args = ', '.join(k + ' = ' + v for k, v in sorted((b.get('arguments') or {}).items()))
            return (b.get('function') or '') + '(' + args + ')' + (' → ' + b['result'] if b.get('result') else '')
        if kind == 'return':
            return T('valore restituito') + ' ' + b['value'] if b.get('value') else T('rientra nel chiamante senza valore')
        if kind == 'loop':
            return F('%@ volte · contatore %@ da 0', b.get('times', ''), b['variable']) if b.get('variable') else F('%@ volte', b.get('times', ''))
        if kind == 'if':
            return T('condizione') + ' ' + (b.get('condition') or '')
        if kind == 'else':
            return T('se la condizione è falsa')
        if kind == 'end':
            return T('fine del blocco')
        if kind == 'set':
            return T('variabile') + ' ' + (b.get('variable') or '') + ' = ' + (b.get('value') or '')
        if kind == 'repeat':
            return F('%lld volte dal blocco %lld', b.get('count') or 2, (b.get('start') or 0) + 1)
        return T('nota nel registro')

    # Plan section -------------------------------------------------------------------------------------
    def _build_plan(self):
        self.plan_widget = QWidget()
        box = QVBoxLayout(self.plan_widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)
        m = self.m
        self.plan_button = button('Pianifica programma', None, lambda: self.replan(self.scenario))
        self.preview_button = button('▶ Anteprima', None, lambda: m.send('studio_movej_play', dict(id=self.slider.plan_id)))
        self.back = button('⏮', None, lambda: self.step(False), 'Istruzione precedente nell’anteprima')
        self.forward = button('⏭', None, lambda: self.step(True), 'Istruzione successiva nell’anteprima')
        self.halt = button('■', None, lambda: m.send('studio_movej_stop'), 'Arresta anteprima')
        self.stepwise = button('Passo passo…', None, lambda: self.execute(True))
        self.run = button('Esegui programma…', 'prominent', lambda: self.execute(False))
        box.addLayout(row(self.plan_button, self.preview_button, self.back, self.forward, self.halt, None, self.stepwise, self.run))
        self.speed_note = label('Applica le velocità modificate prima di pianificare.', 'warning')
        self.home_note = label('Conferma HOME per eseguire il piano; l’anteprima resta disponibile.', 'warning')
        self.problem = label('', 'stop', selectable=True)
        box.addWidget(self.speed_note)
        box.addWidget(self.home_note)
        box.addWidget(self.problem)
        self.exec_box = QWidget()
        self.exec_title = label('', 'accent')
        self.exec_name = caption()
        self.next_step = button('Istruzione successiva', 'prominent', lambda: m.send('studio_program_step'))
        self.continue_button = button('Continua fino alla fine', None, lambda: m.send('studio_program_continue'))
        self.exec_box.setLayout(row(column_layout(self.exec_title, self.exec_name), None, self.next_step, self.continue_button,
                                    button('STOP', 'danger', lambda: m.send('stop'))))
        box.addWidget(self.exec_box)
        self.done = label('', 'accent')
        self.exec_error = label('', 'stop', selectable=True)
        box.addWidget(self.done)
        box.addWidget(self.exec_error)
        self.summary_box = QWidget()
        sb = QVBoxLayout(self.summary_box)
        sb.setContentsMargins(0, 0, 0, 0)
        self.summary = label('', 'section')
        self.samples = caption(small=True)
        self.slider = TimeSlider(m)
        self.decisions = QVBoxLayout()
        self.details = QVBoxLayout()
        sb.addLayout(row(self.summary, None, self.samples))
        sb.addWidget(self.slider)
        sb.addLayout(self.decisions)
        sb.addLayout(self.details)
        box.addWidget(self.summary_box)
        self.add(self.plan_widget)
        self.decision_key = None

    def replan(self, choices):
        self.m.send('studio_program_plan', dict(scenario=choices))

    def boundaries(self, plan):
        stages = plan.get('stages', [])
        result = [0.0]
        for i in range(1, len(stages)):
            if stages[i]['block_index'] != stages[i - 1]['block_index'] or stages[i].get('call_path') != stages[i - 1].get('call_path'):
                result.append(stages[i]['start_time'])
        result.append(plan.get('duration', 0))
        return result

    def step(self, forward):
        plan = self.plan()
        if not plan:
            return
        cursor = self.slider.seconds()
        b = self.boundaries(plan)
        if forward:
            t = next((x for x in b if x > cursor + .001), plan['duration'])
        else:
            t = next((x for x in reversed(b) if x < cursor - .001), 0.0)
        self.m.send('studio_movej_seek', dict(id=plan['id'], elapsed=t))

    def execute(self, stepwise):
        plan = self.plan()
        program = (plan or {}).get('program')
        if not program:
            return
        demo = self.m.state.get('mode') == 'demo'
        text = F('Anteprima: %lld istruzioni, durata stimata %.1f s, con il controllore simulato.' if demo else
                 'ROBOT REALE: %lld istruzioni, durata stimata %.1f s. Il braccio esegue esattamente il piano mostrato, un movimento simultaneo per tratto. Tieni pronto lo STOP.',
                 len(program.get('blocks', [])), plan.get('duration', 0))
        if (program.get('branches') or 0) > 1:
            text += ' ' + F('Il percorso dipende dai sensori: segue uno dei %lld rami verificati.', program['branches'])
        if stepwise:
            text += ' ' + T('Si ferma prima di ogni istruzione: premi «Istruzione successiva» per proseguire.')
        title, accept = ('Eseguire passo passo?', 'Esegui passo passo') if stepwise else ('Eseguire il programma?', 'Esegui programma')
        if confirm(self.window, title, text, accept):
            self.m.send('studio_program_execute', dict(id=plan['id'], confirmed=True, step=stepwise))

    def confirm_simple(self):
        if confirm(self.window, 'Esegui programma?',
                   'Avvio dalla posizione attuale con riferimento valido nella modalità selezionata. Le attese sensore hanno un timeout e i giunti esclusi restano bloccati. Nessuna ripresa automatica dopo un errore.',
                   'Esegui programma'):
            self.m.send('studio_run', dict(confirmed=True))

    def read_json(self):
        self.json.setPlainText(json.dumps(self.blocks(), indent=2, sort_keys=True, ensure_ascii=False))

    def save_json(self):
        try:
            blocks = json.loads(self.json.toPlainText())
            if not isinstance(blocks, list) or not all(isinstance(b, dict) and 'kind' in b and 'name' in b for b in blocks):
                raise ValueError
        except ValueError:
            self.m.set_message(T('Formato dei blocchi non valido.'))
            return
        self.save_blocks(blocks)

    def _fraction(self, value):
        self.fraction_label.setText('%d%%' % value)
        self.m.send('studio_sequence', dict(index=self.preview_pose.currentData() or 0, fraction=value / 100))

    def playback(self):
        return (self.m.studio or {}).get('movej_preview') or {}

    def plan(self):
        plan = self.playback().get('plan')
        return plan if plan and plan.get('program') is not None else None

    def active_block(self, plan, executing):
        playback, s = self.playback(), self.m.studio or {}
        if executing:
            block = playback.get('exec_next_block') if playback.get('step_waiting') else playback.get('exec_block')
            return block if block is not None and block >= 0 else None
        stage = playback.get('stage')
        if plan and playback.get('visual_active') and stage is not None and 0 <= stage < len(plan.get('stages', [])):
            return plan['stages'][stage]['block_index']
        if s.get('program_index', -1) >= 0:
            return s['program_index']
        return None

    def rebuild_list(self, blocks, plan, executing, editable, motion):
        clear_layout(self.list)
        levels = depths(blocks)
        active = self.active_block(plan, executing)
        problem = (self.playback().get('problem') or {}).get('block')
        times = {t['index']: t for t in ((plan or {}).get('program') or {}).get('blocks', [])}
        for i, b in enumerate(blocks):
            marker = b['kind'] in ('else', 'end')
            items = [_spacer(levels[i] * 18)] if levels[i] else []
            enabled = checkbox('')
            enabled.setChecked(b.get('enabled', True))
            enabled.setToolTip(T('Blocco %d' % (i + 1)))
            enabled.clicked.connect(lambda v, k=i: self.set_field(k, 'enabled', v))
            enabled.setVisible(not marker)
            items.append(enabled)
            items.append(label(str(i + 1), 'small'))
            items.append(label(ICONS.get(b['kind'], '□'), 'accent' if b['kind'] in ('movej', 'movel') else 'small'))
            text = QVBoxLayout()
            text.setSpacing(2)
            title = label(b.get('name', ''), 'section', wrap=False)
            detail = caption(self.detail(b, motion), small=True)
            detail.setWordWrap(False)
            text.addWidget(title)
            text.addWidget(detail)
            holder = QWidget()
            holder.setLayout(text)
            if not b.get('enabled', True):
                holder.setStyleSheet('color: gray;')
            items.append(holder)
            items.append(None)
            if i in times:
                items.append(label('%.1f s' % times[i]['duration'], 'mono'))
            if active == i:
                playback = self.playback()
                items.append(label(('⏸' if playback.get('step_waiting') else '⚡') if executing else '▶', 'accent'))
            if problem == i:
                items.append(label('⚠', 'stop'))
            if b['kind'] in ('function', 'call'):
                items.append(button('✎', 'compact', lambda _c=False, bb=b, k=i: self.edit(bb, k), 'Modifica funzione o richiamo'))
            if b['kind'] in ('movej', 'movel'):
                speed = combo([(float(v), '%d%%' % v) for v in range(10, 101, 10)])
                select_combo(speed, float(b.get('speed') or 100))
                speed.setToolTip(T('Velocità rispetto a Muovi e osserva'))
                speed.activated.connect(lambda _x, k=i, w=speed: self.set_field(k, 'speed', w.currentData()))
                items.append(speed)
            up = button('↑', 'compact', lambda _c=False, k=i: self.swap(k, k - 1))
            down = button('↓', 'compact', lambda _c=False, k=i: self.swap(k, k + 1))
            trash = button('🗑', 'compact', lambda _c=False, k=i: self.remove(k),
                           'Elimina funzione e corpo; i richiami rimasti devono essere corretti' if b['kind'] == 'function' else
                           ('Elimina il blocco e la sua Fine; le istruzioni interne restano' if b['kind'] in OPENS else 'Elimina istruzione'))
            up.setEnabled(i > 0)
            down.setEnabled(i < len(blocks) - 1)
            trash.setEnabled(not marker)
            for w in (up, down, trash):
                w.setFixedWidth(34)
            items += [up, down, trash]
            frame = ProgramRow(lambda k=i: self.select(k))
            frame.setLayout(row(*items))
            frame.layout().setContentsMargins(10, 4 if marker else 7, 10, 4 if marker else 7)
            if problem == i:
                state = 'problem'
            elif active == i:
                state = 'active'
            elif self.selected == i:
                state = 'selected'
            elif marker or b['kind'] in OPENS:
                state = 'structure'
            else:
                state = 'plain'
            frame.setProperty('state', state)
            frame.setEnabled(editable)
            self.list.addWidget(frame)

    def rebuild_decisions(self, program, plan, can):
        clear_layout(self.decisions)
        clear_layout(self.details)
        decisions = program.get('decisions') or []
        if decisions:
            box = QVBoxLayout()
            box.addWidget(caption(F('Condizioni sui sensori: %lld rami verificati, %lld campioni. L’esecuzione segue i sensori, sempre su un ramo verificato; l’anteprima mostra il ramo scelto qui.',
                                    program.get('branches') or 1, program.get('checked_samples') or plan.get('sample_count', 0))))
            for d in decisions:
                choice = Segmented([(True, 'Vero'), (False, 'Falso')], bool(d.get('preview')))
                choice.setEnabled(can)
                choice.changed.connect(lambda v, k=d['block_index']: (self.scenario.__setitem__(str(k), v), self.replan(self.scenario)))
                box.addLayout(row(label('⑂', 'accent'), label(F('Istruzione %lld · se %@', d['block_index'] + 1, d['condition']), 'mono'), None,
                                  label('Anteprima'), choice))
            self.decisions.addWidget(well(box, 'Well', 8))
        for item in program.get('lines') or []:
            self.details.addWidget(label(F('Istruzione %lld · retta di %.1f mm in %lld tratti · deviazione massima %.2f mm · arrivo entro %.2f mm',
                                           item['block_index'] + 1, item['length_mm'], item['segments'], item['max_deviation_mm'], item['end_error_mm']), 'mono'))

    def refresh(self):
        m, s = self.m, self.m.studio
        if not s:
            return
        blocks = self.blocks()
        playback = self.playback()
        plan = self.plan()
        executing = bool(playback.get('executing') and plan)
        motion = plan is not None or any(b.get('enabled', True) and b['kind'] in MOTION_KINDS for b in blocks)
        can = ready(m)
        running = bool(playback.get('running'))
        can_preview = bool(plan and playback.get('valid') and can)
        can_execute = bool(can_preview and m.state.get('home') and not running and not m.speed_edits)
        self.title.setText(T('Programma offline · movimenti, cicli e condizioni' if motion else 'Programma a pose registrate'))
        self.running.setText(T('In esecuzione' if s.get('program_running') or executing else 'Da fermo'))
        self.intro.setText(T('Ogni istruzione parte da dove finisce la precedente. Pianifica una volta: anteprima 3D, durata, validazione ed esecuzione usano lo stesso piano, controllato ogni grado. Le velocità sono una percentuale di quelle di Muovi e osserva.' if motion else
                             'Le pose vengono raggiunte direttamente dalla posizione corrente. Aggiungi un’istruzione MoveJ o MoveL per pianificare il programma con anteprima ed esecuzione identiche.'))
        # Editor.
        kind = self.kind.currentData()
        self.kind.setEnabled(self.editing is None)
        self.add_button.setText(T('＋ Aggiungi istruzione' if self.editing is None else 'Salva modifica'))
        self.add_button.setEnabled(not s.get('program_running') and can)
        self.cancel_edit.setVisible(self.editing is not None)
        for k, w in self.options.items():
            w.setVisible(k == kind)
        destination = self.destination.currentData()
        self.movej_target.setVisible(destination == 'target')
        self.movej_pose.setVisible(destination == 'pose')
        targets = [('', 'Scegli')] + [(t['id'], t['name']) for t in self.targets()]
        set_combo_items(self.target, targets, self.target.currentData())
        set_combo_items(self.target_l, targets, self.target_l.currentData())
        poses = [(i, '%d · %s' % (i + 1, p.get('name', ''))) for i, p in enumerate(m.state['sequence'])]
        set_combo_items(self.pose, poses, self.pose.currentData())
        set_combo_items(self.pose2, poses, self.pose2.currentData())
        set_combo_items(self.output, [('', 'Scegli uscita')] + [(o['name'], o['name']) for o in ((s.get('io') or {}).get('outputs') or [])],
                        self.output.currentData())
        set_combo_items(self.called, [('', 'Scegli funzione')] + [(f.get('function', ''), f.get('function', '')) for f in self.functions()],
                        self.called.currentData())
        if kind == 'call' and set(self.argument_edits) != set((self.chosen_function() or {}).get('parameters') or []):
            self.rebuild_arguments()
        elif kind != 'call' and self.argument_edits:
            self.rebuild_arguments()
        self.function_hint.setVisible(kind in ('function', 'call', 'return'))
        self.orientation_row.setVisible(kind in ('movej', 'movel'))
        self.orientation_box.setVisible(kind == 'movej' and destination == 'target')
        self.line_box.setVisible(kind == 'movel')
        self.insert_hint.setVisible(bool(blocks))
        self.insert_hint.setText(T('La nuova istruzione va in fondo. Seleziona una riga per inserirla dopo; subito dopo «Ripeti» o «Se» finisce al loro interno.'
                                   if self.selected is None else 'La nuova istruzione va dopo la riga selezionata.'))
        self.expr_hint.setVisible(kind in ('loop', 'if', 'set'))
        self.target_hint.setVisible(((kind == 'movej' and destination == 'target') or kind == 'movel') and not self.targets())
        self.empty.setVisible(not blocks)
        if self.selected is not None and self.selected >= len(blocks):
            self.selected = None
        editable = not s.get('program_running') and can and self.editing is None
        key = (repr(blocks), repr(((plan or {}).get('program') or {}).get('blocks')), self.active_block(plan, executing),
               (playback.get('problem') or {}).get('block'), self.selected, editable, motion, repr([t['id'] + t['name'] for t in self.targets()]),
               playback.get('step_waiting'), executing)
        if key != self.list_key:
            self.list_key = key
            self.rebuild_list(blocks, plan, executing, editable, motion)
        # Plan section.
        self.plan_widget.setVisible(motion)
        self.simple.setVisible(not motion)
        if motion:
            self.plan_button.setEnabled(can and not running and not m.speed_edits)
            self.preview_button.setEnabled(can_preview and not running)
            self.back.setEnabled(can_preview)
            self.forward.setEnabled(can_preview)
            self.halt.setEnabled(running)
            self.stepwise.setEnabled(can_execute)
            self.run.setEnabled(can_execute)
            self.speed_note.setVisible(bool(m.speed_edits))
            self.home_note.setVisible(bool(plan and not m.state.get('home') and not executing))
            problem = playback.get('problem')
            self.problem.setVisible(bool(problem))
            if problem:
                self.problem.setText('⚠ ' + T(problem.get('where', '')) + '\n' + T(problem.get('detail', '')) + '\n' + angles_text(problem.get('angles', [])))
            self.exec_box.setVisible(executing)
            if executing:
                waiting = bool(playback.get('step_waiting'))
                block = (playback.get('exec_next_block') if waiting else playback.get('exec_block'))
                block = -1 if block is None else block
                self.exec_title.setText(F('In attesa · prossima istruzione %lld' if waiting else 'In esecuzione · istruzione %lld', block + 1) if block >= 0 else '')
                name = (playback.get('exec_next_name') or (blocks[block]['name'] if 0 <= block < len(blocks) else '')) if waiting else (playback.get('exec_name') or '')
                self.exec_name.setText(T(name))
                self.next_step.setVisible(bool(playback.get('step_mode')))
                self.continue_button.setVisible(bool(playback.get('step_mode')))
                self.next_step.setEnabled(waiting)
            self.done.setVisible(bool(playback.get('exec_done') and plan))
            self.done.setText(T('Programma eseguito in Anteprima.' if m.state.get('mode') == 'demo' else
                                'Programma eseguito: DONE dalla Mega per ogni tratto; posizione non misurata.'))
            error = playback.get('exec_error') or ''
            self.exec_error.setVisible(bool(error and plan))
            if error:
                self.exec_error.setText(T('Programma interrotto: ') + T(error) + (' ' if error.endswith('.') else '. ') +
                                        T('Nessuna ripresa automatica: verifica il braccio e ristabilisci HOME.'))
            program = (plan or {}).get('program')
            self.summary_box.setVisible(bool(program))
            if program:
                moves = sum(1 for st in plan.get('stages', []) if st.get('kind') == 'movej' and st.get('axes'))
                self.summary.setText(F('Durata stimata %.1f s · %lld istruzioni · %lld tratti', plan.get('duration', 0), len(program.get('blocks', [])), moves))
                self.samples.setText(F('%lld campioni · passo massimo 1°', plan.get('sample_count', 0)))
                self.slider.show_plan(plan, playback)
                dkey = (repr(program.get('decisions')), repr(program.get('lines')), can and not running, repr(playback.get('exec_decisions')),
                        repr(playback.get('exec_measured')), executing, playback.get('valid'), playback.get('error'))
                if dkey != self.decision_key:
                    self.decision_key = dkey
                    self.rebuild_decisions(program, plan, can and not running)
                    taken = playback.get('exec_decisions') or []
                    if taken:
                        self.details.addWidget(caption(T('Condizioni lette: ') + ' · '.join(
                            F('istruzione %lld %@', t['block_index'] + 1, T('vera' if t['result'] else 'falsa')) for t in taken[-6:]), small=True))
                    measured = playback.get('exec_measured') or []
                    if measured and not executing:
                        self.details.addWidget(label(F('Durata misurata %.2f s · stimata %.2f s', sum(x['actual'] for x in measured),
                                                       sum(x['planned'] for x in measured)), 'mono'))
                    if not playback.get('valid') and not playback.get('exec_done') and not executing and playback.get('error'):
                        self.details.addWidget(label(playback['error'], 'warning'))
        else:
            self.run_simple.setEnabled(bool(m.state.get('home') and m.idle and blocks))
            self.cancel_simple.setEnabled(bool(s.get('program_running')))
            self.simple_error.setVisible(bool(s.get('program_error')))
            self.simple_error.setText(T(s.get('program_error') or ''))
        self.json_buttons.setEnabled(not s.get('program_running') and can and self.editing is None)
        self.validation.refresh()
        enabled_poses = [p for p in m.state['sequence'] if p.get('enabled', True) is not False]
        self.pose_preview.setVisible(not motion and bool(m.state['sequence']))
        set_combo_items(self.preview_pose, [(i, p.get('name', '')) for i, p in enumerate(enabled_poses)], self.preview_pose.currentData())


class ProgramRow(QFrame):
    """One instruction row; a click selects it as the insertion point."""

    def __init__(self, clicked):
        super().__init__()
        self.setObjectName('ProgramRow')
        self.clicked = clicked
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.clicked()
        super().mouseReleaseEvent(event)


class ValidationView(QWidget):
    """Whole-route check of the program or the sequence, with the first problems listed."""

    def __init__(self, m):
        super().__init__()
        self.m = m
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.program = button('✓ Valida programma', None, lambda: m.send('studio_validate', dict(source='program')))
        self.sequence = button('✓ Valida sequenza', None, lambda: m.send('studio_validate', dict(source='sequence', return_home=m.sequence_return_home)))
        layout.addLayout(row(self.program, self.sequence, None))
        layout.addWidget(caption('Verifica le transizioni fra le pose attive dalla posizione attuale, con il ritorno HOME solo se selezionato: limiti, autocollisioni, ostacoli e piano di lavoro ogni grado. Un problema blocca l’avvio della sequenza.'))
        self.result = QVBoxLayout()
        self.result.setSpacing(6)
        layout.addLayout(self.result)
        self.key = None

    def refresh(self):
        idle = self.m.idle
        self.program.setEnabled(idle)
        self.sequence.setEnabled(idle)
        report = (self.m.studio or {}).get('validation')
        key = repr(report)
        if key == self.key:
            return
        self.key = key
        clear_layout(self.result)
        if not report:
            return
        if report.get('ok'):
            self.result.addWidget(label('✓ ' + F('Nessun problema · %lld pose · %lld campioni controllati', report.get('poses', 0), report.get('samples', 0)), 'accent'))
        else:
            issues = report.get('issues') or []
            self.result.addWidget(label('⚠ ' + F('%lld problemi lungo i percorsi · %lld campioni', len(issues), report.get('samples', 0)), 'stop'))
            for issue in issues[:12]:
                self.result.addWidget(well(column_layout(label(issue.get('where', ''), 'section'), caption(issue.get('detail', '')),
                                                         label(angles_text(issue.get('angles', [])), 'mono')), 'Well', 8))
        for note in report.get('notes') or []:
            self.result.addWidget(caption(note, small=True))
