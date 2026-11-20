# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Operator workspace: connection, firmware, limits, joint motion and the taught sequence."""
import json
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QSlider,
                               QSpinBox, QVBoxLayout, QWidget)
from .i18n import F, T
from .model import parse_number, parse_int
from .widgets import (Card, Disclosure, Segmented, button, caption, checkbox, clear_layout, combo, confirm, label, line, row,
                      select_combo, set_combo_items, set_role, set_text_if_idle, well)
from . import theme

GRIPS = [('apri', 'Apri'), ('chiudi', 'Chiudi'), ('non comandata', 'Mantieni')]
DRIVER_LABELS = ['X', 'Y · DM542', 'Z', 'E0', 'E1', 'EXT']
STEP_PRESETS = [1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 270, 360]
LIMIT_PRESETS = [0, 5, 15, 30, 45, 90, 180, 360]


class ConnectionPanel(Card):
    def __init__(self, m, window):
        super().__init__('Connessione e riferimento')
        self.m, self.window = m, window
        self.mode = combo([('demo', 'Anteprima'), ('robot', 'Robot USB')], self._mode)
        self.port = combo([('', 'Nessuna porta')], self._port)
        self.add(row(label('Modalità'), self.mode, None, label('Porta'), self.port))
        self.connect_button = button('Avvia anteprima', 'prominent', self.connect)
        self.disconnect_button = button('Scollega controllo', None, lambda: m.send('disconnect'))
        self.home_button = button('Imposta riferimento HOME…', None, self.set_home)
        self.home_label = label('Riferimento HOME valido', 'accent')
        self.add(row(self.connect_button, self.disconnect_button, self.home_button, self.home_label, None))
        self.add(caption('HOME è la posizione fisica iniziale scelta da te. Gli angoli sono calcolati dagli impulsi, senza encoder.'))
        self.collisions = checkbox('Blocca interferenze modello · Operatore')
        self.collisions.clicked.connect(self._collisions)
        self.collision_note = caption()
        self.guidance = label('', 'accent')
        self.usb_note = caption()
        self.show_firmware = button('Mostra firmware da caricare', None, self._show_firmware)
        self.add(self.collisions, self.collision_note, self.guidance, self.usb_note, row(self.show_firmware, None))

    def _mode(self, value):
        self.m.mode = value
        self.refresh()

    def _port(self, value):
        self.m.port = value

    def connect(self):
        if self.m.mode == 'robot' and not confirm(self.window, 'Connessione al robot reale',
                                                  'Questa azione apre la porta seriale selezionata. Procedi solo quando hai predisposto i collegamenti e vuoi controllare il robot reale.',
                                                  'Connetti Mega'):
            return
        self.window.reset_drafts()
        self.m.connect_now()

    def set_home(self):
        demo = self.m.state['mode'] == 'demo'
        text = ('Confermi lo zero virtuale? L’anteprima non apre la seriale e non controlla il robot.' if demo else
                'Il braccio è fisicamente nella posa iniziale? La conferma azzera gli angoli e abilita la tenuta dei motori. Sostieni il braccio durante la prima abilitazione.')
        if confirm(self.window, 'Conferma HOME', text):
            self.m.send('home_set')

    def _collisions(self, enabled):
        if enabled:
            self.m.send('studio_operator_collisions', dict(enabled=True))
        elif confirm(self.window, 'Interferenze modello solo come avvisi?',
                     'Per sequenze, pose e HOME dell’Operatore il controllo collisioni del modello 3D non bloccherà i movimenti. Verifica visivamente il percorso reale. Limiti, velocità, comunicazione e STOP restano attivi. MoveJ/MoveL nello Studio mantengono i controlli. La scelta si azzera alla prossima connessione.',
                     'Usa solo avvisi'):
            self.m.send('studio_operator_collisions', dict(enabled=False, confirmed=True))
        self.refresh()

    def _show_firmware(self):
        from .app import open_path
        open_path(self.window, 'RegiaDemo')

    def refresh(self):
        m, s = self.m, self.m.state
        select_combo(self.mode, m.mode)
        set_combo_items(self.port, [('', 'Nessuna porta')] + [(p, p) for p in s.get('ports', [])], m.port)
        if m.port and m.port not in s.get('ports', []):
            m.port = ''
            select_combo(self.port, '')
        self.port.setEnabled(m.mode == 'robot')
        self.connect_button.setText(T('Avvia anteprima') if m.mode == 'demo' else T('Connetti Mega'))
        busy = m.firmware.get('busy')
        self.connect_button.setEnabled(m.idle and not busy and (m.mode == 'demo' or bool(m.port)))
        self.disconnect_button.setVisible(bool(s.get('connected')))
        self.disconnect_button.setEnabled(m.idle and not busy)
        self.home_label.setVisible(bool(s.get('home')))
        self.home_button.setVisible(not s.get('home'))
        self.home_button.setEnabled(bool(s.get('connected') and s.get('identified') and s.get('speed_confirmed') and m.idle and not busy))
        checks = s.get('operator_collision_checks') is not False
        self.collisions.setChecked(checks)
        self.collisions.setEnabled(m.idle and not busy)
        self.collision_note.setText(T('Il modello 3D può bloccare sequenze e HOME. Disattiva solo per passare ad avvisi in questa sessione; limiti, velocità e STOP restano attivi.') if checks else
                                    T('SOLO AVVISI: sequenze, pose e HOME non vengono bloccati dalle interferenze del modello 3D. Controlla il percorso reale. Studio MoveJ/MoveL resta verificato.'))
        set_role(self.collision_note, 'caption' if checks else 'warning')
        self.guidance.setText(T(s.get('guidance', '')))
        robot = s.get('mode') == 'robot' and s.get('connected')
        self.usb_note.setVisible(bool(robot))
        self.usb_note.setText(T('Firmware riconosciuto. La USB alimenta la logica della Mega; non alimenta i motori. Per provare i movimenti servono anche le alimentazioni esterne dei driver.') if s.get('identified') else
                              T('USB aperta non significa robot pronto. Con sola USB usa Anteprima: i motori non hanno alimentazione e le pose reali non sono verificabili.'))
        self.show_firmware.setVisible(bool(robot and not s.get('identified')))


class FirmwarePanel(Card):
    def __init__(self, m, window):
        super().__init__('Firmware · Arduino Mega 2560')
        self.m, self.window = m, window
        group = Disclosure('Carica il firmware direttamente dall’app')
        self.add(group)
        group.add(caption('Firmware incluso: Regia 4 · Mega 2560 + RAMPS 1.4. J2 usa il DM542 esterno; servo su D11.'))
        self.status = label('', 'accent')
        self.disconnect_note = label('Prima premi Scollega controllo. Per il caricamento prepara la Mega con sola USB e senza alimentazione dei motori.', 'warning')
        self.boards = combo([('', 'Seleziona una porta')], self._board)
        self.scan = button('Aggiorna porte', None, lambda: self.action('scan'))
        self.compile = button('Verifica compilazione', None, lambda: self.action('compile'))
        self.upload = button('Carica sulla Mega', 'prominent', self.confirm_upload)
        self.setup = button('Prepara dipendenze…', None, self.prepare)
        self.cancel = button('Annulla operazione', None, lambda: m.send('firmware_cancel'))
        self.tool = caption(small=True)
        self.tool.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.missing = QWidget()
        missing = QVBoxLayout(self.missing)
        missing.setContentsMargins(0, 0, 0, 0)
        missing.addWidget(caption('Serve Arduino CLI con il core Arduino AVR e AccelStepper. Puoi installare la CLI senza Arduino IDE.'))
        link = label('<a href="https://docs.arduino.cc/arduino-cli/installation">' + T('Installa Arduino CLI dal sito ufficiale') + '</a>')
        link.setOpenExternalLinks(True)
        missing.addWidget(link)
        missing.addLayout(row(button('Ricontrolla strumenti', None, lambda: self.action('scan')), None))
        self.tools = QWidget()
        tools = QVBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.addLayout(row(self.scan, self.boards, None))
        tools.addLayout(row(self.compile, self.upload, self.setup, self.cancel, None))
        tools.addWidget(caption('L’editor Arduino non viene aperto. Aggiorna le porte, scegli la Mega e conferma il caricamento. Al termine il controllo resta scollegato.'))
        tools.addWidget(self.tool)
        self.error = label('', 'warning', selectable=True)
        logs = Disclosure('Log compilazione e caricamento')
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setFixedHeight(180)
        logs.add(self.logs)
        group.add(self.status, self.disconnect_note, self.tools, self.missing, self.error, logs)

    def _board(self, value):
        self.m.firmware_port = value
        self.refresh()

    def action(self, operation):
        self.m.send('firmware', dict(operation=operation, port=getattr(self.m, 'firmware_port', ''), confirmed=operation == 'upload'))

    def confirm_upload(self):
        port = getattr(self.m, 'firmware_port', '')
        if confirm(self.window, 'Carica firmware sulla Mega?',
                   T('Scriverò il firmware salvato nel workspace su ') + port + T('. Conferma che è la Mega 2560. Il caricamento sostituisce il programma e riavvia la scheda: predisponi il braccio e togli l’alimentazione dei motori. Chiudi eventuali monitor seriali. Dopo dovrai riconnettere e ristabilire HOME.'),
                   'Carica firmware'):
            self.action('upload')

    def prepare(self):
        if confirm(self.window, 'Prepara strumenti firmware',
                   'Scarica tramite Arduino CLI il core Arduino AVR 1.8.8 e AccelStepper 1.64. Serve Internet. Non carica nulla sulla scheda.',
                   'Scarica dipendenze'):
            self.action('setup')

    def refresh(self):
        m, f = self.m, self.m.firmware
        can_work = not m.state.get('connected') and m.idle and not f.get('busy')
        self.status.setText(T(f.get('status', '')))
        self.disconnect_note.setVisible(bool(m.state.get('connected')))
        self.tools.setVisible(bool(f.get('available')))
        self.missing.setVisible(not f.get('available'))
        port = getattr(m, 'firmware_port', '')
        set_combo_items(self.boards, [('', 'Seleziona una porta')] + [(b['port'], T(b['name']) + ' · ' + b['port']) for b in f.get('boards', [])], port)
        for widget in (self.scan, self.boards, self.compile, self.setup):
            widget.setEnabled(can_work)
        self.upload.setEnabled(can_work and any(b['port'] == port and b.get('compatible') for b in f.get('boards', [])))
        self.cancel.setVisible(bool(f.get('busy') and f.get('phase') != 'uploading'))
        self.tool.setText(T('Strumento: ') + f.get('tool', ''))
        self.error.setText(T(f.get('error', '')))
        self.error.setVisible(bool(f.get('error')))
        text = '\n'.join(f.get('logs', []))
        if self.logs.toPlainText() != text:
            self.logs.setPlainText(text)
            self.logs.verticalScrollBar().setValue(self.logs.verticalScrollBar().maximum())


class FirmwareEditorPanel(Card):
    def __init__(self, m, window):
        super().__init__('Firmware · parametri ed editor')
        self.m, self.window = m, window
        self.summary = label('', 'mono')
        self.status = caption()
        self.upgrade_note = label('Aggiorna i sorgenti per includere ENABLE e movimento simultaneo; poi compila e carica esplicitamente.', 'warning')
        self.upgrade = button('Aggiorna comandi giunti…', None, self.upgrade_axes)
        self.add(self.summary, self.status, row(self.upgrade_note, self.upgrade))
        self.group = Disclosure('Microstepping, riduttori e sorgenti')
        self.add(self.group)
        self.name = line('Nome profilo')
        self.group.add(self.name)
        self.axes_grid = QGridLayout()
        self.axes_grid.setHorizontalSpacing(8)
        for col, text in enumerate(['', 'Driver', 'Passi/giro', 'Microstep ×', 'Riduzione :1', '', 'imp/°']):
            self.axes_grid.addWidget(caption(text, small=True), 0, col)
        self.axis_rows = []
        for i in range(6):
            driver = combo([('DM542', 'DM542')] if i in (1, 5) else [('A4988', 'A4988'), ('DRV8825', 'DRV8825')])
            steps, micro, ratio = line(width=80), line(width=80), line(width=80)
            invert = checkbox('Inverti')
            rate = caption(small=True)
            for col, widget in enumerate([label('J%d' % (i + 1), 'section'), driver, steps, micro, ratio, invert, rate]):
                self.axes_grid.addWidget(widget, i + 1, col)
            for w in (steps, micro, ratio):
                w.textChanged.connect(self._rates)
            self.axis_rows.append(dict(driver=driver, steps=steps, micro=micro, ratio=ratio, invert=invert, rate=rate))
        self.group.add(self.axes_grid)
        self.j6_active = checkbox('J6 fisico · driver esterno')
        self.j6_pins = [line('Pin', 50), line('Pin', 50), line('−1', 50)]
        self.group.add(row(self.j6_active, label('STEP'), self.j6_pins[0], label('DIR'), self.j6_pins[1], label('ENA'), self.j6_pins[2], None))
        self.group.add(caption('−1 = non collegato. Pin disponibili: 40, 42, 44, 57, 58, 59, 63–66; verificane l’uso sugli accessori. Per DM542 lascia ENA a −1. J6 resta disponibile in Anteprima anche senza driver.', small=True))
        self.group.add(caption('Microstep 8 significa 1/8: jumper e DIP fisici devono corrispondere. La riduzione è giri motore / giro uscita, ad esempio 38,4. Corrente e alimentazione restano regolazioni hardware. Mega/RAMPS con DM542 su J2 e J6 esterno opzionale; nessuna sesta uscita motore è presente sulla RAMPS.'))
        self.group.add(row(button('Genera e salva dai parametri…', 'prominent', self.generate), button('Rileggi profilo', None, self.load),
                           button('Ripristina firmware originale…', None, self.restore), button('Esporta sorgenti…', None, self.export), None))
        self.file = combo([])
        self.file.activated.connect(lambda _i: self.read(self.file.currentData()))
        self.editor = QPlainTextEdit()
        self.editor.setFixedHeight(280)
        font = self.editor.font()
        font.setFamilies(['Menlo', 'Consolas', 'DejaVu Sans Mono', 'monospace'])
        font.setPointSize(11)
        self.editor.setFont(font)
        self.group.add(row(label('File'), self.file, button('Rileggi file', None, lambda: self.read(self.m.firmware_file)), None,
                           button('Salva sorgente', 'prominent', self.save)))
        self.group.add(self.editor)
        self.group.add(caption('Il salvataggio conserva una revisione precedente. Verifica compilazione e Carica sulla Mega usano questi file salvati. Modifiche libere possono rendere il firmware incompatibile: controlla watchdog, pin, limiti e identificazione. Nessuna scrittura sulla scheda avviene salvando.'))
        self.group.add(row(button('Verifica compilazione', None, lambda: window.panels['firmware'].action('compile')),
                           button('Apri cartella sorgenti', None, self.open_folder), None))
        self.error = label('', 'stop')
        self.group.add(self.error)
        self.identity = None
        self.loaded_text = None
        self.group.toggled.connect(lambda open_: open_ and self.read(self.m.firmware_file))

    def editable(self):
        m = self.m
        return not m.state.get('connected') and m.idle and not m.firmware.get('busy')

    def load(self):
        w = self.m.firmware_workspace
        if not w:
            return
        p = w['profile']
        self.name.setText(p.get('name', ''))
        for i, a in enumerate(p.get('axes', [])[:6]):
            r = self.axis_rows[i]
            select_combo(r['driver'], a.get('driver'))
            r['steps'].setText(str(a.get('steps', '')))
            r['micro'].setText(str(a.get('microstep', '')))
            r['ratio'].setText('%g' % a.get('reduction', 1))
            r['invert'].setChecked(bool(a.get('invert')))
            if i == 5:
                self.j6_active.setChecked(bool(a.get('active')))
                for edit, key in zip(self.j6_pins, ('step_pin', 'dir_pin', 'enable_pin')):
                    edit.setText(str(a.get(key, -1)))
        self._rates()

    def _rates(self):
        for r in self.axis_rows:
            s, mi, ra = parse_int(r['steps'].text(), 1, 100000), parse_int(r['micro'].text(), 1, 256), parse_number(r['ratio'].text())
            r['rate'].setText('%.2f %s' % (s * mi * ra / 360, T('imp/°')) if s and mi and ra else '')

    def profile(self):
        axes = []
        for i, r in enumerate(self.axis_rows):
            s, mi, ra = parse_int(r['steps'].text(), -10 ** 9, 10 ** 9), parse_int(r['micro'].text(), -10 ** 9, 10 ** 9), parse_number(r['ratio'].text())
            if s is None or mi is None or ra is None:
                raise ValueError(T('Compila passi/giro, microstep e riduzione con numeri validi.'))
            axis = dict(driver=r['driver'].currentData(), steps=s, microstep=mi, reduction=ra, invert=r['invert'].isChecked())
            if i == 5:
                pins = [parse_int(e.text(), -1, 69) for e in self.j6_pins]
                if None in pins:
                    raise ValueError(T('Completa STEP, DIR ed ENA con pin validi (−1 se non collegato).'))
                axis.update(active=self.j6_active.isChecked(), step_pin=pins[0], dir_pin=pins[1], enable_pin=pins[2])
            else:
                original = (self.m.firmware_workspace or {}).get('profile', {}).get('axes', [{}] * 6)[i]
                for key in ('active', 'step_pin', 'dir_pin', 'enable_pin'):
                    if key in original:
                        axis[key] = original[key]
            axes.append(axis)
        return dict(schema=1, name=self.name.text(), board='mega2560', axes=axes)

    def generate(self):
        try:
            profile = self.profile()
        except ValueError as e:
            self.error.setText(str(e))
            return
        self.error.setText('')
        if confirm(self.window, 'Generare il firmware dai parametri?',
                   'Salvo una revisione e aggiorno le costanti dei sei canali nel sorgente. La Mega non viene caricata. Conferma che i valori corrispondono ai driver e ai riduttori reali.',
                   'Genera e salva'):
            self.m.send('firmware_generate', dict(profile=profile), lambda ok, _r: ok and self.read('RegiaDemo.ino'))

    def upgrade_axes(self):
        if confirm(self.window, 'Aggiornare i comandi dei giunti?',
                   'Salvo una revisione, sostituisco il file RegiaDemo.ino con quello incluso e rigenero il tuo profilo, mantenendo microstep, riduzioni, versi e pin. Eventuali modifiche manuali al file restano nella revisione. La Mega non viene caricata.',
                   'Aggiorna sorgente'):
            self.m.send('firmware_upgrade_axes', None, lambda ok, _r: ok and (self.load(), self.read(self.m.firmware_file)))

    def restore(self):
        if confirm(self.window, 'Ripristinare i sorgenti originali?', 'La versione corrente resta nelle revisioni locali. Nessun caricamento sulla Mega.', 'Ripristina'):
            self.m.send('firmware_restore', None, lambda ok, _r: ok and (self.load(), self.read(self.m.firmware_file)))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self.window, T('Esporta sorgenti…'), 'firmware-robot.zip', 'ZIP (*.zip)')
        if path:
            self.m.send('firmware_export', dict(path=path))

    def read(self, name):
        if name:
            self.m.send('firmware_read', dict(name=name), lambda ok, _r: ok and self._show_text())

    def _show_text(self):
        self.loaded_text = self.m.firmware_text
        self.editor.setPlainText(self.m.firmware_text)

    def save(self):
        self.m.send('firmware_save', dict(name=self.m.firmware_file, text=self.editor.toPlainText()))

    def open_folder(self):
        w = self.m.firmware_workspace
        if w:
            QDesktopServices.openUrl(QUrl.fromLocalFile(w['folder']))

    def refresh(self):
        w = self.m.firmware_workspace
        self.setVisible(w is not None)
        if not w:
            return
        if w.get('identity') != self.identity:
            self.identity = w.get('identity')
            self.load()
        self.summary.setText('%s · ID %s · %s %.1f°/s' % (w['profile'].get('name', ''), w.get('identity', ''), T('massimo calcolato'), w.get('max_speed', 0)))
        set_role(self.summary, 'mono')
        self.status.setText(T(w.get('status', '')))
        outdated = w.get('axis_control_source') is not True or w.get('multi_axis_source') is not True
        self.upgrade_note.setVisible(outdated)
        self.upgrade.setVisible(outdated)
        self.upgrade.setEnabled(self.editable())
        self.group.content.setEnabled(self.editable())
        set_combo_items(self.file, [(f, f) for f in w.get('files', [])], self.m.firmware_file)
        if w.get('error'):
            self.error.setText(T(w['error']))


class LimitsPanel(Card):
    def __init__(self, m, window):
        super().__init__('Limiti dei giunti')
        self.m, self.window = m, window
        self.preset = combo([(span, 'Bloccato · 0°' if span == 0 else '±%d°' % span) for span in LIMIT_PRESETS])
        select_combo(self.preset, 5)
        self.restore_button = button('Riprendi ultimi', None, self.restore)
        self.apply_button = button('Applica limiti', 'prominent', self.apply)
        self.add(row(label('Predefinito'), self.preset, button('Per tutti i giunti', None, lambda: self.set_preset(self.preset.currentData())), None,
                     self.restore_button, self.apply_button))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.minima, self.maxima = [], []
        for i in range(6):
            lo, hi = line('Minimo', text='0'), line('Massimo', text='0')
            menu = combo([(None, 'Predefinito')] + [(span, 'Blocca a 0°' if span == 0 else '±%d°' % span) for span in LIMIT_PRESETS])
            menu.activated.connect(lambda _x, axis=i, w=menu: (w.currentData() is not None and self.set_preset(w.currentData(), axis), w.setCurrentIndex(0)))
            box = QVBoxLayout()
            box.addWidget(label('J%d' % (i + 1), 'section'))
            box.addWidget(lo)
            box.addWidget(hi)
            box.addWidget(menu)
            grid.addWidget(well(box), i // 3, i % 3)
            self.minima.append(lo)
            self.maxima.append(hi)
        self.add(grid)
        self.add(caption('Scegli o modifica gli intervalli, poi premi Applica limiti. I predefiniti non sono finecorsa meccanici. Gli ultimi limiti restano separati per Anteprima e Robot USB.'))

    def reset(self):
        for e in self.minima + self.maxima:
            e.setText('0')

    def set_preset(self, span, axis=None):
        for i in ([axis] if axis is not None else range(6)):
            self.minima[i].setText(str(-span))
            self.maxima[i].setText(str(span))

    def restore(self):
        limits = self.m.last_limits.get(self.m.limits_mode())
        if not limits or len(limits) not in (5, 6):
            return
        limits = limits + [[0, 0]] * (6 - len(limits))
        for i in range(6):
            self.minima[i].setText('%g' % limits[i][0])
            self.maxima[i].setText('%g' % limits[i][1])
        self.m.set_message(T('Ultimi limiti recuperati nei campi: premi Applica limiti per usarli.'))

    def apply(self):
        limits, pos = [], self.m.state['pos']
        for i in range(6):
            lo, hi = parse_number(self.minima[i].text()), parse_number(self.maxima[i].text())
            if lo is None or hi is None:
                self.m.set_message(F('Completa J%d con un numero valido. Puoi usare punto o virgola.', i + 1))
                return
            if not (-360 <= lo <= 0 <= hi <= 360 and lo <= pos[i] <= hi):
                self.m.set_message(F('J%d: i limiti devono contenere HOME (0°) e la posizione attuale, entro −360° e +360°.', i + 1))
                return
            limits.append([lo, hi])
        self.m.send('limits', dict(limits=limits))

    def refresh(self):
        m = self.m
        self.restore_button.setEnabled(m.limits_mode() in m.last_limits)
        self.apply_button.setEnabled(bool(m.state.get('connected')) and m.idle)
        self.setEnabled(not m.firmware.get('busy'))


class JointCard(QWidget):
    def __init__(self, m, window, axis):
        super().__init__()
        self.m, self.window, self.axis = m, window, axis
        self.frame = well(QVBoxLayout(), 'WellIdle')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)
        body = self.frame.layout()
        body.setSpacing(8)
        self.enabled = checkbox('J%d' % (axis + 1))
        self.enabled.clicked.connect(self._enable)
        self.enabled.setToolTip(T('Togli la spunta per escludere il giunto e disattivare ENABLE, se collegato. Dopo il rilascio conferma di nuovo HOME.'))
        body.addLayout(row(self.enabled, None, caption(DRIVER_LABELS[axis], small=True)))
        self.value = label('0.00°', 'value')
        body.addWidget(self.value)
        self.minus = button('−', None, lambda: m.jog(axis, -1))
        self.plus = button('+', None, lambda: m.jog(axis, 1))
        self.jog_row = QWidget()
        jr = QHBoxLayout(self.jog_row)
        jr.setContentsMargins(0, 0, 0, 0)
        jr.addWidget(self.minus)
        jr.addWidget(self.plus)
        body.addWidget(self.jog_row)
        self.multi_row = QWidget()
        mr = QHBoxLayout(self.multi_row)
        mr.setContentsMargins(0, 0, 0, 0)
        self.multi = line('0', 72, '0')
        self.multi.textChanged.connect(lambda _t: window.panels['motion'].multi_changed())
        mr.addWidget(caption('Spostamento'))
        mr.addStretch(1)
        mr.addWidget(self.multi)
        mr.addWidget(label('°'))
        body.addWidget(self.multi_row)
        self.peak = caption(small=True)
        body.addWidget(self.peak)
        self.speed_label = caption('Velocità', small=True)
        body.addWidget(self.speed_label)
        self.speed = line('°/s', 72)
        self.speed.returnPressed.connect(self.apply_speed)
        self.speed.textEdited.connect(lambda _t: self._dirty())
        body.addLayout(row(self.speed, caption('°/s'), None, button('✓', None, self.apply_speed, 'Applica velocità giunto')))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(2, 40)  # half degrees per second
        self.slider.valueChanged.connect(self._slide)
        self.slider.sliderReleased.connect(self.apply_speed)
        body.addWidget(self.slider)
        self.stop = button('■ STOP J%d' % (axis + 1), 'danger', lambda: m.send('axis_stop', dict(axis=axis)),
                           'Arresta questo giunto mantenendo la tenuta. La sequenza in corso viene interrotta se questo è il giunto attivo.')
        body.addWidget(self.stop)
        self.status = caption(small=True)
        self.limits = caption(small=True)
        body.addWidget(self.status)
        body.addWidget(self.limits)
        self.synced = None

    def _enable(self, value):
        m, s, axis = self.m, self.m.state, self.axis
        can_release = (s.get('mode') == 'robot' and s.get('connected') and (s.get('drive_caps') or [False] * 6)[axis] is True
                       and (s.get('drive_state') or [None] * 6)[axis] is not False)
        if not value and can_release:
            m.send('axis_stop', dict(axis=axis))
            if confirm(self.window, 'Rilascia la tenuta del giunto?',
                       'Il movimento è stato fermato se il giunto era attivo. Disabilitare ENABLE toglie la corrente alle bobine: un asse sotto carico può cadere. Sostienilo prima di confermare. La sequenza verrà interrotta e HOME dovrà essere ristabilita.',
                       'Disabilita ENABLE', destructive=True):
                m.send('joint_enable', dict(axis=axis, enabled=False))
        else:
            m.send('joint_enable', dict(axis=axis, enabled=value))
        self.refresh()

    def applied_speed(self):
        s = self.m.state
        return min((s.get('axis_speeds') or [5.0] * 6)[self.axis], s.get('max_speed', 20))

    def _dirty(self):
        value = parse_number(self.speed.text())
        if value is not None and abs(value - self.applied_speed()) < .005:
            self.m.speed_edits.discard(self.axis)
        else:
            self.m.speed_edits.add(self.axis)

    def _slide(self, value):
        if self.slider.isSliderDown():
            self.speed.setText('%.1f' % (value / 2))
            self._dirty()

    def apply_speed(self):
        submitted = self.speed.text()
        value = parse_number(submitted)
        if value is None or not 1 <= value <= self.m.state.get('max_speed', 20):
            self.m.set_message(T('Velocità da 1 al massimo indicato, in gradi/s.'))
            return

        def done(ok, _reply):
            if ok and self.speed.text() == submitted:
                self.sync_speed(force=True)
            else:
                self._dirty()
        self.m.send('set_axis_speed', dict(axis=self.axis, speed=value), done)

    def sync_speed(self, force=False):
        speed = self.applied_speed()
        if force or (not self.speed.hasFocus() and not self.slider.isSliderDown() and self.axis not in self.m.speed_edits):
            self.speed.setText('%.2f' % speed)
            self.slider.blockSignals(True)
            self.slider.setValue(int(round(speed * 2)))
            self.slider.blockSignals(False)
            self.m.speed_edits.discard(self.axis)

    def status_text(self):
        s, axis = self.m.state, self.axis
        enabled = (s.get('axes_enabled') or [True] * 6)[axis]
        supported = s.get('mode') == 'demo' or s.get('axis_control') is True
        if not s.get('connected'):
            return 'Driver non connesso'
        if s.get('mode') == 'demo':
            return 'Enable simulato' if enabled else 'Escluso in anteprima'
        if (s.get('axes_available') or [True] * 6)[axis] is False:
            return 'Driver esterno da configurare'
        if not supported:
            return 'ENABLE richiede firmware aggiornato'
        if axis in (s.get('pending_off') or []):
            return 'Disattivazione in attesa…'
        if (s.get('drive_caps') or [False] * 6)[axis] is not True:
            return 'ENA non collegato · coppia possibile'
        state = (s.get('drive_state') or [None] * 6)[axis]
        if state is not None:
            return 'Driver in tenuta' if state else 'ENABLE disattivato'
        return 'Stato ENABLE da confermare'

    def refresh(self):
        m, s, axis = self.m, self.m.state, self.axis
        enabled = (s.get('axes_enabled') or [True] * 6)[axis]
        supported = s.get('mode') == 'demo' or s.get('axis_control') is True
        self.enabled.setChecked(enabled)
        self.enabled.setEnabled(not ((not m.idle and not enabled) or (s.get('connected') and not supported)))
        self.value.setText('%.2f°' % s['pos'][axis])
        self.jog_row.setVisible(not m.multi_mode)
        self.multi_row.setVisible(m.multi_mode)
        self.multi_row.setEnabled(m.idle and enabled and (s.get('axes_available') or [True] * 6)[axis] is not False)
        plan = m.multi_plan or {}
        show_peak = m.multi_mode and plan.get('valid') and axis < len(plan.get('peaks', []))
        self.peak.setVisible(bool(show_peak))
        if show_peak:
            self.peak.setText(T('Picco previsto: ') + '%.2f°/s' % plan['peaks'][axis])
        self.minus.setEnabled(m.can_jog(axis, -1))
        self.plus.setEnabled(m.can_jog(axis, 1))
        self.speed_label.setText(T('Velocità massima' if m.multi_mode else 'Velocità'))
        self.speed.setEnabled(m.idle)
        self.slider.setEnabled(m.idle)
        self.slider.setMaximum(int(s.get('max_speed', 20) * 2))
        key = (tuple(s.get('axis_speeds') or []), s.get('max_speed'))
        if key != self.synced:
            self.synced = key
            self.sync_speed()
        self.stop.setEnabled(bool(s.get('connected')))
        status = self.status_text()
        self.status.setText(T(status))
        set_role(self.status, 'warning' if s.get('mode') == 'robot' and (s.get('drive_caps') or [None] * 6)[axis] is False else 'small')
        low, high = s['limits'][axis]
        self.limits.setText(T('Giunto bloccato') if low == high else '%.0f° … %.0f°' % (low, high))
        active = s.get('active_axis') == axis or axis in (s.get('active_axes') or [])
        name = 'WellActive' if active else 'WellIdle'
        if self.frame.objectName() != name:
            self.frame.setObjectName(name)
            self.frame.style().unpolish(self.frame)
            self.frame.style().polish(self.frame)


class MotionPanel(Card):
    def __init__(self, m, window):
        super().__init__('Muovi e osserva')
        self.m, self.window = m, window
        self.speed_value = label('5.0°/s', 'accent')
        self.common = QSlider(Qt.Horizontal)
        self.common.setRange(2, 40)
        self.common.setValue(10)
        self.common.valueChanged.connect(lambda v: self.speed_value.setText('%.1f°/s' % (v / 2)))
        self.max_label = caption('20°/s')
        self.apply_all = button('Applica a tutti', None, lambda: m.send('set_speed', dict(speed=self.common.value() / 2)))
        self.add(row(label('Velocità comune', 'section'), None, self.speed_value))
        self.add(row(caption('1°/s'), self.common, self.max_label))
        self.add(row(self.apply_all, caption('Stesse velocità per comandi singoli, simultanei e pose'), None))
        self.mode = Segmented([(False, 'Singolo'), (True, 'Simultaneo')])
        self.mode.changed.connect(self._mode)
        self.add(self.mode)
        # Single-joint step controls.
        self.single = QWidget()
        sl = QVBoxLayout(self.single)
        sl.setContentsMargins(0, 0, 0, 0)
        self.keyboard = combo([])
        self.keyboard.setToolTip(T('Option + freccia sinistra/destra: sposta il giunto selezionato'))
        self.keyboard.activated.connect(lambda _i: setattr(m, 'keyboard_axis', self.keyboard.currentData()))
        self.step_value = label('1.00°', 'accent')
        self.step_text = line('Gradi', 75, '1')
        self.step_text.returnPressed.connect(self.apply_step)
        self.stepper = QSpinBox()
        self.stepper.setRange(1, 360)
        self.stepper.valueChanged.connect(lambda v: self.select_step(v) if v != int(m.step) else None)
        sl.addLayout(row(label('Spostamento per clic', 'section'), self.keyboard, self.step_value, None, self.step_text, label('°'),
                         button('Imposta angolo', None, self.apply_step), self.stepper))
        self.step_slider = QSlider(Qt.Horizontal)
        self.step_slider.setRange(1, 360)
        self.step_slider.valueChanged.connect(lambda v: self.select_step(v) if self.step_slider.isSliderDown() else None)
        sl.addLayout(row(caption('1°'), self.step_slider, caption('360°')))
        presets = QGridLayout()
        presets.setSpacing(6)
        self.preset_buttons = {}
        for i, amount in enumerate(STEP_PRESETS):
            b = button('%d°' % amount, 'compact', lambda _c=False, a=amount: self.select_step(a))
            b.setCheckable(True)
            presets.addWidget(b, i // 8 if window.width() < 1300 else 0, i % 8 if window.width() < 1300 else i)
            self.preset_buttons[amount] = b
        sl.addLayout(presets)
        self.add(self.single)
        self.speed_note = caption('Per abilitare 20°/s sul robot, carica il firmware incluso dalla sezione Firmware. Quello attuale resta utilizzabile fino a 10°/s.')
        self.add(self.speed_note)
        self.add(caption('Il passo è lo spostamento per clic; la velocità è in gradi al secondo. − e + restano disponibili solo entro i limiti applicati.'))
        self.add(caption('I movimenti simultanei rispettano le velocità massime dei giunti e possono rallentare per il budget impulsi totale. STOP su un giunto del gruppo ferma l’intero gruppo mantenendo la tenuta.'))
        self.extra = checkbox('Canali aggiuntivi · J6 se non associato al modello', self._extra)
        self.add(self.extra)
        joints = QHBoxLayout()
        joints.setSpacing(14)
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(10)
        self.cards = {i: JointCard(m, window, i) for i in range(6)}
        joints.addLayout(self.cards_grid, 3)
        from .studio import ArmPanel
        self.arm = ArmPanel(m, window, compact=True)
        self.arm.setMinimumHeight(560)
        joints.addWidget(self.arm, 2)
        self.add(joints)
        self.axes_key = None
        self.layout_cards()
        # Simultaneous group.
        self.multi_box = well(QVBoxLayout())
        mb = self.multi_box.layout()
        mb.addWidget(label('Movimento simultaneo', 'accent'))
        mb.addWidget(caption('Imposta lo spostamento nelle schede J1–J6 e regola la velocità con gli stessi controlli del movimento singolo. Zero lascia fermo il giunto.'))
        self.multi_info = caption()
        self.multi_speed = label('Applica le velocità modificate con Invio o ✓ prima di muovere il gruppo.', 'warning')
        self.multi_go = button('Muovi insieme…', 'prominent', self.move_together)
        mb.addWidget(self.multi_info)
        mb.addWidget(self.multi_speed)
        mb.addLayout(row(self.multi_go, button('Azzera spostamenti', None, self.clear_multi), None))
        mb.addWidget(caption('Registra posa conserva il gruppo simultaneo. Le sequenze collegano le pose attive direttamente. I comandi manuali simultanei rispettano limiti e velocità, senza controllo collisioni del modello.'))
        self.add(self.multi_box)
        from .voice import VoiceMotionControls
        self.voice = VoiceMotionControls(m, window)
        self.add(self.voice)
        self.grip_row = QWidget()
        self.grip_state = caption()
        self.grip_note = caption(small=True)
        self.grip_row.setLayout(row(label('Pinza', 'section'), button('Apri pinza', None, lambda: m.send('servo', dict(command='apri'))),
                                    button('Chiudi pinza', None, lambda: m.send('servo', dict(command='chiudi'))), self.grip_state, None, self.grip_note))
        self.add(self.grip_row)
        self.multi_timer = QTimer(self)
        self.multi_timer.setSingleShot(True)
        self.multi_timer.setInterval(150)
        self.multi_timer.timeout.connect(lambda: m.request_multi_plan([self.cards[i].multi.text() for i in range(6)]))
        self.multi_key = None
        self.axes_key = None

    def layout_cards(self):
        axes = self.m.control_axes()
        if axes == self.axes_key:
            return
        self.axes_key = axes
        for card in self.cards.values():
            card.setParent(None)
        for index, axis in enumerate(axes):
            self.cards_grid.addWidget(self.cards[axis], index // 2, index % 2)
        if self.m.keyboard_axis not in axes:
            self.m.keyboard_axis = axes[0]
        set_combo_items(self.keyboard, [(a, 'J%d' % (a + 1)) for a in axes], self.m.keyboard_axis)

    def _mode(self, value):
        self.m.multi_mode = value
        self.multi_changed()
        self.window.refresh()

    def _extra(self, value):
        self.m.show_extra_joints = value
        self.layout_cards()

    def select_step(self, value):
        self.m.step = float(value)
        self.step_text.setText('%g' % value)
        self.refresh()

    def apply_step(self):
        value = parse_number(self.step_text.text())
        if value is None or not 1 <= value <= 360:
            self.m.set_message(T('Inserisci uno spostamento da 1° a 360°.'))
            return
        self.select_step(round(value * 100) / 100)

    def multi_changed(self):
        self.multi_timer.start()

    def clear_multi(self):
        for card in self.cards.values():
            card.multi.setText('0')

    def move_together(self):
        plan = self.m.multi_plan
        if not plan or not plan.get('valid'):
            return
        lines = [F('J%d %+.2f° · massimo %.2f°/s · picco previsto %.2f°/s', a + 1, plan['deltas'][a], plan['requested'][a], plan['peaks'][a])
                 for a in plan['axes']]
        text = '\n'.join(lines) + F('\nTempo previsto: %.2f s', plan['duration'])
        if confirm(self.window, 'Esegui movimento simultaneo?', text, 'Esegui'):
            self.m.send('multi_jog', dict(deltas=plan['deltas'], context=plan['context']))

    def refresh(self):
        m, s = self.m, self.m.state
        self.layout_cards()
        max_speed = s.get('max_speed', 20)
        self.common.setMaximum(int(max_speed * 2))
        self.max_label.setText('%d°/s' % max_speed)
        self.apply_all.setEnabled(bool(s.get('connected') and s.get('identified') and m.idle))
        self.mode.set_value(m.multi_mode)
        self.mode.setEnabled(m.idle)
        self.single.setVisible(not m.multi_mode)
        self.step_value.setText('%.2f°' % m.step)
        for amount, b in self.preset_buttons.items():
            b.setChecked(m.step == amount)
        self.stepper.blockSignals(True)
        self.stepper.setValue(int(m.step))
        self.stepper.blockSignals(False)
        if not self.step_slider.isSliderDown():
            self.step_slider.blockSignals(True)
            self.step_slider.setValue(int(m.step))
            self.step_slider.blockSignals(False)
        self.speed_note.setVisible(max_speed < 20)
        self.extra.setEnabled(m.idle)
        for card in self.cards.values():
            if card.parent() is not None:
                card.refresh()
        self.arm.refresh()
        # Plans depend on positions, limits and speeds: refresh them when those change.
        key = (m.multi_mode, tuple(s['pos']), repr(s['limits']), repr(s.get('axis_speeds')), s.get('max_speed'),
               repr(s.get('axes_enabled')), s.get('multi_axis'), s.get('home'), s.get('busy'))
        if key != self.multi_key:
            self.multi_key = key
            if m.multi_mode:
                self.multi_changed()
        self.multi_box.setVisible(m.multi_mode)
        plan = m.multi_plan
        if plan:
            if plan.get('valid'):
                text = T('Tempo previsto: ') + '%.2f s' % plan['duration']
                if plan.get('budget_limited'):
                    text += ' · ' + T('Velocità ridotte dal budget impulsi')
                self.multi_info.setText(text)
            else:
                self.multi_info.setText(T(plan.get('error', '')))
        else:
            self.multi_info.setText('')
        self.multi_speed.setVisible(bool(m.speed_edits))
        self.multi_go.setEnabled(bool(s.get('home') and m.idle and plan and plan.get('valid') and not m.speed_edits))
        self.voice.refresh()
        self.grip_state.setText(T(s.get('grip', '')))
        self.grip_note.setText(T('Posizioni virtuali' if s.get('mode') == 'demo' else 'Posizioni stimate · senza encoder'))
        self.grip_row.setEnabled(bool(s.get('home') and m.idle))
        self.setEnabled(not m.firmware.get('busy'))


class PoseEditor(QDialog):
    def __init__(self, m, window, index, revision, pose):
        super().__init__(window)
        self.m, self.index, self.revision = m, index, revision
        self.setWindowTitle(T('Modifica posa'))
        self.setMinimumWidth(680)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        self.enabled = checkbox('Abilitata')
        self.enabled.setChecked(pose.get('enabled', True) is not False)
        layout.addLayout(row(label('Modifica posa', 'headline'), None, self.enabled))
        self.name = line('Nome posa', text=pose.get('name', ''))
        layout.addWidget(self.name)
        layout.addWidget(label('Angoli assoluti rispetto a HOME', 'section'))
        self.angles = [line('Gradi', text='%.2f' % v) for v in pose.get('pos', [0] * 6)]
        layout.addLayout(row(*[_labelled('J%d' % (i + 1), e) for i, e in enumerate(self.angles)]))
        self.dwell = line('Secondi', 90, '%g' % pose.get('dwell', 0))
        self.grip = combo(GRIPS)
        select_combo(self.grip, pose.get('grip') or 'non comandata')
        layout.addLayout(row(label('Pausa'), self.dwell, label('secondi'), None, label('Pinza'), self.grip))
        layout.addWidget(caption('Salvare modifica la sequenza. Gli angoli nuovi sostituiscono il target della posa; il collegamento alla posa successiva è diretto e simultaneo. Verifica questi tratti prima di riprodurli sul robot; i limiti saranno ricontrollati all’avvio.'))
        self.error = label('', 'stop')
        layout.addWidget(self.error)
        self.save_button = button('Salva modifiche', 'prominent', self.save)
        layout.addLayout(row(button('Annulla', None, self.reject), None, self.save_button))

    def save(self):
        name = self.name.text().strip()
        if not 1 <= len(name) <= 60:
            self.error.setText(T('Scrivi un nome da 1 a 60 caratteri.'))
            return
        seconds = parse_number(self.dwell.text())
        if seconds is None or not 0 <= seconds <= 60:
            self.error.setText(T('Pausa da 0 a 60 secondi.'))
            return
        values = []
        for i, edit in enumerate(self.angles):
            v = parse_number(edit.text())
            if v is None or not -360 <= v <= 360:
                self.error.setText(F('J%d: inserisci un angolo da −360° a +360°.', i + 1))
                return
            values.append(round(v * 100) / 100)
        self.save_button.setEnabled(False)

        def done(ok, reply):
            self.save_button.setEnabled(True)
            if ok:
                self.accept()
            else:
                self.error.setText(T(reply.get('error') or 'Salvataggio non riuscito.'))
        self.m.send('pose_update', dict(index=self.index, revision=self.revision, name=name, pos=values, dwell=seconds,
                                        grip=self.grip.currentData(), enabled=self.enabled.isChecked()), done)


def _labelled(text, widget):
    box = QVBoxLayout()
    box.setSpacing(4)
    box.addWidget(label(text, 'accent'))
    box.addWidget(widget)
    return box


class SequenceMotionEditor(QDialog):
    def __init__(self, m, window, motion):
        super().__init__(window)
        self.m = m
        self.setWindowTitle(T('Ordine dei giunti nella sequenza'))
        self.setMinimumWidth(550)
        layout = QVBoxLayout(self)
        layout.addWidget(label('Ordine dei giunti nella sequenza', 'headline'))
        self.mode = Segmented([('simultaneous', 'Simultaneo'), ('ordered', 'Un giunto alla volta')], motion.get('mode', 'simultaneous'))
        self.mode.changed.connect(lambda _v: self.rebuild())
        layout.addWidget(self.mode)
        layout.addWidget(caption('L’ordine vale per ogni passaggio tra le pose e per il ritorno a HOME se selezionato a fine ciclo.'))
        self.order = list(motion.get('order', range(6)))
        self.pauses = [line('Secondi', 65, '%g' % p) for p in motion.get('pauses', [0] * 6)]
        self.rows = QVBoxLayout()
        layout.addLayout(self.rows)
        self.note = caption('Pausa da 0 a 60 secondi. Si applica solo quando c’è un altro giunto da muovere.')
        layout.addWidget(self.note)
        self.error = label('', 'stop')
        layout.addWidget(self.error)
        self.save_button = button('Salva', 'prominent', self.save)
        layout.addLayout(row(None, button('Annulla', None, self.reject), self.save_button))
        self.rebuild()

    def rebuild(self):
        clear_layout(self.rows)
        ordered = self.mode.value == 'ordered'
        self.note.setVisible(ordered)
        if not ordered:
            return
        for index, axis in enumerate(self.order):
            pause = self.pauses[axis]
            up = button('↑', None, lambda _c=False, i=index: self.swap(i, i - 1))
            down = button('↓', None, lambda _c=False, i=index: self.swap(i, i + 1))
            up.setEnabled(index > 0)
            down.setEnabled(index < len(self.order) - 1)
            holder = QWidget()
            holder.setLayout(row(label('%d.' % (index + 1)), label('J%d' % (axis + 1), 'section'), None, label('Pausa dopo il giunto'), pause, label('s'), up, down))
            self.rows.addWidget(holder)

    def swap(self, a, b):
        self.order[a], self.order[b] = self.order[b], self.order[a]
        for pause in self.pauses:
            pause.setParent(None)
        self.rebuild()

    def save(self):
        values = [parse_number(p.text()) for p in self.pauses]
        if any(v is None or not 0 <= v <= 60 for v in values):
            set_role(self.note, 'warning')
            return

        def done(ok, reply):
            if ok:
                self.accept()
            else:
                self.error.setText(T(reply.get('error', '')))
        self.m.send('studio_sequence_motion', dict(motion=dict(mode=self.mode.value, order=self.order, pauses=values)), done)


class SequencePanel(Card):
    def __init__(self, m, window):
        super().__init__('La tua sequenza')
        self.m, self.window = m, window
        self.motion_label = caption()
        self.order_label = label('', 'mono')
        self.order_button = button('Ordine dei giunti…', None, self.edit_motion)
        self.add(row(self.order_button, self.motion_label, self.order_label, None))
        self.name = line('Nome posa')
        self.dwell = line('Secondi', 65, '1')
        self.grip = combo([('auto', 'Ultimo comando')] + GRIPS)
        self.record = button('＋ Registra posa', 'prominent', self.record_pose)
        self.add(row(self.name, caption('Pausa'), self.dwell, label('s'), self.grip, self.record))
        self.hint = caption()
        self.add(self.hint)
        self.add(caption('La pinza viene comandata all’arrivo nella posa. Solo le pose attive sono destinazioni; i vecchi passaggi registrati non vengono riprodotti. Mantieni non invia comandi alla pinza.'))
        self.count = caption()
        self.add(self.count)
        self.undo = button('Annulla ultima modifica pose', None, lambda: m.send('pose_undo', dict(revision=m.state['sequence_revision'])))
        self.add(row(self.undo, None))
        self.list = QVBoxLayout()
        self.list.setSpacing(2)
        self.add(self.list)
        self.preview = button('Anteprima sequenza', None, lambda: m.send('studio_movej_plan', dict(source='sequence', return_home=m.sequence_return_home)))
        self.play_preview = button('Riproduci anteprima', None, self._play_preview)
        self.stop_preview = button('Arresta anteprima', None, lambda: m.send('studio_movej_stop'))
        self.duration = label('', 'mono')
        self.add(row(self.preview, self.play_preview, self.stop_preview, self.duration, None))
        self.ordered_note = caption('La vista 3D mostra i giunti associati al modello.')
        self.warnings = label('Operatore · interferenze modello SOLO AVVISI', 'warning')
        self.return_home = checkbox('Torna a HOME a fine sequenza')
        self.return_home.toggled.connect(lambda v: setattr(m, 'sequence_return_home', v))
        self.add(self.ordered_note, self.warnings, self.return_home)
        self.once = button('▶ Una volta', 'prominent', lambda: self.play(False))
        self.repeat = button('↻ Ripeti', None, lambda: self.play(True))
        self.pause = button('Pausa', None, lambda: m.send('pause'))
        self.end_cycle = button('Termina questo ciclo', None, lambda: m.send('end_cycle'))
        self.go_home = button('Vai a HOME…', None, self.prepare_home)
        self.clear = button('Svuota', None, self.clear_sequence)
        self.add(row(self.once, self.repeat, self.pause, self.end_cycle, None, self.go_home, self.clear))
        self.add(caption('Il ciclo parte dalla posizione attuale e termina sull’ultima posa. Il ritorno a HOME avviene se selezionato. La pinza mantiene l’ultima richiesta.'))
        self.list_key = None

    def edit_motion(self):
        SequenceMotionEditor(self.m, self.window, self.motion()).exec()

    def motion(self):
        return self.m.state.get('sequence_motion') or dict(mode='simultaneous', order=list(range(6)), pauses=[0.0] * 6)

    def record_pose(self):
        pause = parse_number(self.dwell.text())
        if pause is None or not 0 <= pause <= 60:
            self.m.set_message(T('La pausa deve essere da 0 a 60 secondi.'))
            return
        name = self.name.text().strip() or 'Posa %d' % (len(self.m.state['sequence']) + 1)
        self.m.send('record', dict(name=name, dwell=pause, grip=self.grip.currentData()))

    def _play_preview(self):
        plan = ((self.m.studio or {}).get('movej_preview') or {}).get('plan') or {}
        self.m.send('studio_movej_play', dict(id=plan.get('id')))

    def play(self, repeat):
        m = self.m

        def planned(ok, _reply):
            context = m.plan_context()
            if not ok or not context:
                return
            motion = m.state.get('sequence_motion') or {}
            if motion.get('mode') == 'ordered':
                text = ' → '.join('J%d' % (a + 1) for a in motion['order']) + '\n' + T('Da una posa all’altra si muove un giunto alla volta, con le pause impostate.')
            else:
                text = 'Partenza dalla posizione attuale. Le pose attive vengono raggiunte nell’ordine visibile, con giunti simultanei.'
            if confirm(self.window, 'Riproduci la sequenza', text, 'Esegui'):
                m.send('play', {'repeat': repeat, 'return_home': m.sequence_return_home, 'context': context})
        m.plan('sequence', planned, return_home=m.sequence_return_home)

    def prepare_home(self):
        m = self.m

        def planned(ok, _reply):
            context = m.plan_context()
            if ok and context and confirm(self.window, 'Ritorno diretto a HOME',
                                          'Il ritorno collega la posizione attuale a zero con i giunti simultanei. Non ripercorre le vecchie pose o i jog. Controlla la traccia 3D e il percorso reale prima di confermare.',
                                          'Esegui ritorno'):
                m.send('home', dict(context=context))
        m.plan('home', planned)

    def clear_sequence(self):
        if confirm(self.window, 'Svuota sequenza', 'Le pose salvate saranno cancellate.', 'Svuota', destructive=True):
            self.m.send('clear')

    def rebuild_list(self):
        m, s = self.m, self.m.state
        clear_layout(self.list)
        if not s['sequence']:
            self.list.addWidget(caption('La sequenza è vuota. Registra la prima posa per iniziare.'))
            return
        revision = s['sequence_revision']
        for i, pose in enumerate(s['sequence']):
            enabled = pose.get('enabled', True) is not False
            box = QVBoxLayout()
            box.setSpacing(6)
            switch = checkbox('')
            switch.setChecked(enabled)
            switch.setToolTip(F('Abilita posa %lld', i + 1))
            switch.clicked.connect(lambda v, i=i: m.send('pose_enable', dict(index=i, enabled=v, revision=revision)))
            grip = combo(GRIPS)
            select_combo(grip, pose.get('grip') or 'non comandata')
            grip.activated.connect(lambda _x, i=i, g=grip: m.send('pose_grip', dict(index=i, grip=g.currentData(), revision=revision)))
            edit = button('Modifica', None, lambda _c=False, i=i, p=pose: PoseEditor(m, self.window, i, revision, p).exec())
            up = button('↑', None, lambda _c=False, i=i: m.send('pose_move', dict(index=i, target=i - 1, revision=revision)), 'Sposta posa prima')
            down = button('↓', None, lambda _c=False, i=i: m.send('pose_move', dict(index=i, target=i + 1, revision=revision)), 'Sposta posa dopo')
            delete = button('🗑', None, lambda _c=False, i=i: m.send('pose_delete', dict(index=i, revision=revision)), 'Elimina questa posa')
            up.setEnabled(i > 0 and m.idle)
            down.setEnabled(i < len(s['sequence']) - 1 and m.idle)
            for w in (switch, grip, edit, delete):
                w.setEnabled(m.idle)
            title = label(pose.get('name', ''), 'section', wrap=False)
            items = [switch, label(str(i + 1), 'accent'), title]
            if not enabled:
                items.append(caption('Esclusa'))
            if pose.get('angles_edited'):
                items.append(label('Angoli modificati', 'accent'))
            items += [None, edit, grip, up, down, delete, caption('%.1f s' % pose.get('dwell', 0))]
            box.addLayout(row(*items))
            box.addWidget(label(' · '.join('J%d %.2f°' % (j + 1, v) for j, v in enumerate(pose.get('pos', []))), 'small'))
            frame = well(box, 'Well' if i % 2 == 0 else 'WellPlain', 10)
            self.list.addWidget(frame)

    def refresh(self):
        m, s = self.m, self.m.state
        motion = self.motion()
        ordered = motion.get('mode') == 'ordered'
        self.motion_label.setText(T('Un giunto alla volta' if ordered else 'Simultaneo'))
        self.order_label.setText(' → '.join('J%d' % (a + 1) for a in motion.get('order', [])) if ordered else '')
        self.order_button.setEnabled(m.idle)
        self.record.setEnabled(bool(s.get('home') and m.idle))
        self.hint.setText(T('Muovi con − e +, poi registra la posa con tutti e sei i giunti e la richiesta della pinza.' if s.get('home') else
                            'Conferma HOME e applica i limiti per muovere il robot e registrare le pose.'))
        active = sum(1 for p in s['sequence'] if p.get('enabled', True) is not False)
        self.count.setText(F('%lld di %lld pose abilitate. Le pose escluse non aggiungono tappe, pausa o pinza.', active, len(s['sequence'])))
        self.undo.setEnabled(m.idle and bool(s.get('can_undo')))
        key = (repr(s['sequence']), s['sequence_revision'], m.idle)
        if key != self.list_key:
            self.list_key = key
            self.rebuild_list()
        playback = (m.studio or {}).get('movej_preview') or {}
        plan = playback.get('plan') or {}
        has_plan = plan.get('source') == 'sequence' and playback.get('valid')
        self.preview.setEnabled(m.idle and not m.speed_edits and active > 0 and not playback.get('running'))
        self.play_preview.setVisible(bool(has_plan and not playback.get('running')))
        self.play_preview.setEnabled(m.idle)
        self.stop_preview.setVisible(bool(has_plan and playback.get('running')))
        self.duration.setText(F('Durata stimata %.1f s', plan.get('duration', 0)) if has_plan else '')
        self.ordered_note.setVisible(ordered)
        self.warnings.setVisible(s.get('operator_collision_checks') is False)
        self.return_home.setChecked(m.sequence_return_home)
        self.return_home.setEnabled(m.idle)
        can_play = bool(s.get('home') and m.idle and active)
        self.once.setEnabled(can_play)
        self.repeat.setEnabled(can_play)
        self.pause.setText(T('Riprendi' if s.get('paused') else 'Pausa'))
        self.pause.setEnabled(bool(s.get('playing')))
        self.end_cycle.setVisible(bool(s.get('playing')))
        self.go_home.setEnabled(bool(s.get('home') and m.idle))
        self.clear.setEnabled(m.idle)
        self.setEnabled(not m.firmware.get('busy'))
