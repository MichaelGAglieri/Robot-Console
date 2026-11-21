# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Main window: header, workspaces, sidebars, quit flow."""
import os, sys, time
from pathlib import Path
from PySide6.QtCore import QEvent, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QIcon, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLineEdit, QListWidget, QMainWindow, QPlainTextEdit,
                               QScrollArea, QSplitter, QSplitterHandle, QStackedWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget, QAbstractSpinBox,
                               QComboBox)
from . import __version__, i18n, theme
from .i18n import F, T
from .model import AppModel
from .widgets import (Segmented, StatusChip, button, caption, checkbox, choose, clear_layout, combo, confirm, icon_label, label, retint, row,
                      select_combo, tinted, well)

ROOT = Path(__file__).resolve().parents[1]
WORKSPACES = [('operator', 'Operatore'), ('studio', 'Studio 3D e programmi'), ('diagnostics', 'Diagnostica e ROS 2'), ('assistant', 'Assistente')]
i18n.add({'Importa pezzi EB-15…': 'Import EB-15 parts…',
          'Usa i file STL originali di ToolBox Robotics (EB-15 ed EBG-30) per generare il modello dettagliato solo su questo computer.':
              'Uses the original ToolBox Robotics STL files (EB-15 and EBG-30) to build the detailed model on this computer only.',
          'Per il modello dettagliato importa gli STL originali EB-15 ed EBG-30 di ToolBox Robotics (licenza CC BY-NC-ND): restano solo su questo computer.':
              'For the detailed model import the original ToolBox Robotics EB-15 and EBG-30 STL files (CC BY-NC-ND licence): they stay on this computer only.',
          'Scegli gli STL o gli ZIP scaricati da Thingiverse (EB-15 e EBG-30)': 'Choose the STL files or ZIP archives downloaded from Thingiverse (EB-15 and EBG-30)',
          'Trascina: ruota · Maiusc + trascina: sposta · rotella o pizzico: zoom': 'Drag: orbit · Shift + drag: pan · wheel or pinch: zoom',
          'Scrivi «sì confermo» oppure «annulla»': 'Type “yes confirm” or “cancel”', 'Conferma': 'Confirm',
          'Dettatura locale non disponibile: installa i pacchetti facoltativi vosk e sounddevice. Puoi scrivere il comando.':
              'Local dictation unavailable: install the optional vosk and sounddevice packages. You can type the command.',
          'Dettatura locale: manca il modello Vosk della lingua scelta (vedi Guida). Puoi scrivere il comando.':
              'Local dictation: the Vosk model for the chosen language is missing (see the Guide). You can type the command.',
          'Ti ascolto.': 'Listening.', 'Microfono non disponibile: ': 'Microphone unavailable: ',
          'Sintesi vocale non disponibile su questo sistema.': 'Speech synthesis is unavailable on this system.',
          'Per il riconoscimento QR installa opencv-python (facoltativo).': 'For QR recognition install opencv-python (optional).',
          'QtMultimedia non disponibile in questa installazione di PySide6.': 'QtMultimedia is not available in this PySide6 installation.',
          'Token copiato negli appunti.': 'Token copied to the clipboard.', 'Salvataggio non riuscito.': 'Saving failed.',
          'Salvate automaticamente su questo computer. Restano separate dai progetti esportati e dalla memoria dell’IA.':
              'Saved automatically on this computer. They stay separate from exported projects and from the AI memory.',
          'Uso solo modelli già presenti sul computer; nessun download automatico.': 'Only models already on this computer are used; nothing is downloaded automatically.',
          'All’invio di una domanda con IA attiva avvio Ollama e carico il modello scelto. Uso solo modelli già presenti sul computer; nessun download automatico.':
              'When a question is sent with AI on, Ollama starts and the chosen model is loaded. Only models already on this computer are used; nothing is downloaded automatically.',
          'Il robot non è fermo a HOME': 'The robot is not stopped at HOME'})


def open_path(window, relative):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / relative)))


class TitleRow(QWidget):
    def __init__(self, m):
        super().__init__()
        self.m = m
        self.cycles = caption()
        self.setLayout(row(_column(label('Insegna un gesto. Ripetilo.', 'title', wrap=False),
                                   label('Controllo locale · sei canali articolari · una sequenza da presentare', 'caption', wrap=False)), None, self.cycles))

    def refresh(self):
        self.cycles.setText(F('%lld cicli completati', self.m.state.get('cycle', 0)))


def _column(*widgets):
    layout = QVBoxLayout()
    layout.setSpacing(6)
    for w in widgets:
        layout.addWidget(w)
    return layout


class Page(QScrollArea):
    """One workspace: a vertical column of panels, refreshed only while visible."""

    def __init__(self, m, panels):
        super().__init__()
        self.setObjectName('Content')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName('Canvas')
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        self.panels = [TitleRow(m)] + panels
        for p in self.panels:
            layout.addWidget(p)
        layout.addStretch(1)
        self.setWidget(holder)

    def refresh(self):
        for p in self.panels:
            p.refresh()


class SessionSidebar(QFrame):
    def __init__(self, m, window):
        super().__init__()
        self.m, self.window = m, window
        self.setObjectName('Sidebar')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        title = label(T('Attività del robot').upper(), wrap=False)
        title.setObjectName('SidebarTitle')
        layout.addLayout(row(icon_label('list'), title, None, spacing=7))
        self.status = caption()
        layout.addWidget(self.status)
        self.follow = checkbox('Segui ultimi eventi')
        self.follow.setProperty('role', 'caption')
        self.follow.setChecked(True)
        layout.addWidget(self.follow)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.events = QVBoxLayout(holder)
        self.events.setSpacing(10)
        self.scroll.setWidget(holder)
        layout.addWidget(self.scroll, 1)
        bar = self.scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _a, b: self.follow.isChecked() and bar.setValue(b))
        self.follow.toggled.connect(lambda v: v and bar.setValue(bar.maximum()))
        rule = QFrame()
        rule.setObjectName('CardRule')
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        section = label('Sessione e chiusura', wrap=False)
        section.setObjectName('SidebarSection')
        layout.addWidget(section)
        self.quit = button('HOME e chiudi l’app', None, window.close)
        layout.addWidget(self.quit)
        layout.addWidget(caption('Torna a HOME e verifica la posizione prima di uscire.', small=True))
        self.key = None

    def refresh(self):
        m = self.m
        self.status.setText(T(m.connection_status()))
        self.quit.setEnabled(not m.firmware.get('busy'))
        events = m.state.get('robot_events') or []
        key = (events[-1]['id'] if events else None, len(events), i18n.language())
        if key == self.key:
            return
        self.key = key
        clear_layout(self.events)
        if not events:
            self.events.addWidget(caption('Il diario della sessione comparirà qui.'))
        for e in events:
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addLayout(row(caption(time.strftime('%H:%M:%S', time.localtime(e['time'])), small=True), None,
                              caption('Anteprima' if e.get('mode') == 'demo' else 'Robot USB', small=True)))
            text = label(e.get('text', ''), 'mono', selectable=True)
            box.addWidget(text)
            self.events.addWidget(well(box, 'WellEvent', 9))
        self.events.addStretch(1)


class OperatorNotes(QFrame):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setObjectName('Sidebar')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = label(T('Note operatore').upper(), wrap=False)
        title.setObjectName('SidebarTitle')
        layout.addLayout(row(icon_label('note'), title, None, spacing=7))
        layout.addWidget(caption('Appunti, misure e idee per la sessione.'))
        self.text = QPlainTextEdit(settings.value('operatorNotes', '', str))
        self.text.setObjectName('Notes')
        self.text.textChanged.connect(lambda: settings.setValue('operatorNotes', self.text.toPlainText()))
        layout.addWidget(self.text, 1)
        layout.addWidget(caption('Salvate automaticamente su questo computer. Restano separate dai progetti esportati e dalla memoria dell’IA.', small=True))

    def refresh(self):
        pass


class Guide(QDialog):
    """Offline manual: docs/USER_GUIDE(.en).md split by chapter, with search."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(T('Guida completa Robot Console'))
        self.resize(1000, 700)
        name = 'USER_GUIDE.en.md' if i18n.language() == 'en' else 'USER_GUIDE.md'
        try:
            self.source = (ROOT / 'docs' / name).read_text(encoding='utf-8')
        except OSError:
            self.source = ''
        self.sections = self.split(self.source)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addLayout(row(_column(label('Guida completa Robot Console', 'title'), caption('Manuale offline · funzioni, procedure ed esempi')), None,
                             button('Salva manuale…', None, self.save), button('Chiudi', None, self.reject)))
        self.query = QLineEdit()
        self.query.setPlaceholderText(T('Cerca nella guida…'))
        self.query.textChanged.connect(self.filter)
        layout.addWidget(self.query)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setFixedWidth(250)
        self.list.currentRowChanged.connect(self.show_section)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        body.addWidget(self.list)
        body.addWidget(self.view, 1)
        layout.addLayout(body, 1)
        self.previous = button('Capitolo precedente', None, lambda: self.list.setCurrentRow(self.list.currentRow() - 1))
        self.next = button('Capitolo successivo', None, lambda: self.list.setCurrentRow(self.list.currentRow() + 1))
        self.count = label('', 'mono')
        layout.addLayout(row(self.previous, self.next, None, self.count))
        self.matches = []
        self.filter('')

    @staticmethod
    def split(text):
        result, title, body = [], '', []
        for line in text.splitlines():
            if line.startswith('## '):
                if title:
                    result.append((title, '\n'.join(body)))
                title, body = line[3:], []
            elif title:
                body.append(line)
        if title:
            result.append((title, '\n'.join(body)))
        return result

    def filter(self, text):
        text = text.strip().lower()
        self.matches = [s for s in self.sections if not text or text in (s[0] + '\n' + s[1]).lower()]
        self.list.blockSignals(True)
        self.list.clear()
        for title, _ in self.matches:
            self.list.addItem(title)
        self.list.blockSignals(False)
        self.count.setText('%d / %d' % (len(self.matches), len(self.sections)))
        if self.matches:
            self.list.setCurrentRow(0)
        else:
            self.view.setPlainText(T('Nessun risultato. Prova un’altra parola.'))
        self.show_section(self.list.currentRow())

    def show_section(self, index):
        if 0 <= index < len(self.matches):
            title, content = self.matches[index]
            self.view.setMarkdown('# ' + title + '\n\n' + content)
        self.previous.setEnabled(index > 0)
        self.next.setEnabled(0 <= index < len(self.matches) - 1)

    def save(self):
        from PySide6.QtWidgets import QFileDialog
        name = 'Robot-Console-User-Guide.en.md' if i18n.language() == 'en' else 'Robot-Console-Guida.md'
        path, _ = QFileDialog.getSaveFileName(self, T('Salva manuale…'), name, 'Markdown (*.md)')
        if path:
            Path(path).write_text(self.source, encoding='utf-8')


class LineHandle(QSplitterHandle):
    """5-point hit area drawn as a 1-point line, like the macOS sidebar dividers."""

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.width() // 2, 0, 1, self.height(), theme.color('border'))

    def mouseDoubleClickEvent(self, _event):
        splitter = self.splitter()
        sizes = splitter.sizes()
        index = splitter.indexOf(self)
        side = 0 if index == 1 else len(sizes) - 1  # double click: default sidebar width
        delta = 220 - sizes[side]
        sizes[side] = 220
        sizes[1] -= delta
        splitter.setSizes(sizes)


class LineSplitter(QSplitter):
    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setHandleWidth(5)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return LineHandle(self.orientation(), self)


class MainWindow(QMainWindow):
    def __init__(self, m, settings):
        super().__init__()
        self.m, self.settings = m, settings
        self.allow_quit = False
        self.setWindowTitle('Robot Console')
        self.setMinimumSize(1040, 720)
        self.panels = {}
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        rule = QFrame()
        rule.setObjectName('HeaderRule')
        rule.setFixedHeight(2)
        outer.addWidget(rule)
        bar = QFrame()
        bar.setObjectName('Workspace')
        self.workspace = Segmented(WORKSPACES, settings.value('workspace', 'operator', str), segment_width=150)
        self.workspace.changed.connect(self.set_workspace)
        area = label('Area di lavoro', wrap=False)
        area.setObjectName('WorkspaceLabel')
        bar.setLayout(row(None, area, self.workspace, None, spacing=12))
        bar.layout().setContentsMargins(20, 10, 20, 10)
        outer.addWidget(bar)
        self.banner = QFrame()
        self.banner.setObjectName('Banner')
        self.banner_text = label('', selectable=True)
        self.banner.setLayout(row(label('⚠'), self.banner_text, None))
        self.banner.layout().setContentsMargins(12, 9, 12, 9)
        outer.addWidget(_padded(self.banner))
        self.approval = ApprovalBanner(m)
        outer.addWidget(_padded(self.approval))
        self.splitter = LineSplitter()
        self.session = SessionSidebar(m, self)
        self.notes = OperatorNotes(settings)
        for side in (self.session, self.notes):
            side.setMinimumWidth(200)
            side.setMaximumWidth(340)
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.session)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.notes)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        sizes = settings.value('splitter', None)
        self.splitter.setSizes([int(x) for x in sizes] if sizes else [220, 1000, 220])
        self.splitter.splitterMoved.connect(lambda *_: settings.setValue('splitter', self.splitter.sizes()))
        outer.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        self._pages()
        self._menus()
        self.session.setVisible(settings.value('showSession', True, bool))
        self.notes.setVisible(settings.value('showNotes', True, bool))
        self.events_toggle.setChecked(self.session.isVisible())
        self.notes_toggle.setChecked(self.notes.isVisible())
        self.set_workspace(self.workspace.value, save=False)
        m.updated.connect(self.refresh)
        m.message_changed.connect(self._message)
        m.quit_ready.connect(self.force_quit)
        escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape.activated.connect(self.stop)
        geometry = settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1440, 850)
        self.refresh()

    # Construction ------------------------------------------------------------------------------------
    def _header(self):
        header = QFrame()
        header.setObjectName('Header')
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)
        mark = icon_label('cpu', 'ink', 17)
        mark.setObjectName('BrandMark')
        mark.setFixedSize(30, 30)
        brand = label('ROBOT CONSOLE', wrap=False)
        brand.setObjectName('Brand')
        layout.addWidget(mark)
        layout.addWidget(brand)
        layout.addStretch(1)
        self.status_chip = StatusChip()
        self.mode_chip = StatusChip()
        layout.addWidget(self.status_chip)
        layout.addWidget(self.mode_chip)
        sep = QFrame()
        sep.setObjectName('HeaderSeparator')
        sep.setFixedSize(1, 24)
        layout.addWidget(sep)
        self.events_toggle = button('Eventi', 'header', None, 'Mostra o nascondi attività del robot', icon='sidebar-left')
        self.notes_toggle = button('Note', 'header', None, 'Mostra o nascondi note operatore', icon='sidebar-right')
        for b in (self.events_toggle, self.notes_toggle):
            b.setCheckable(True)
        self.events_toggle.toggled.connect(lambda v: self.toggle_sidebar(self.session, 'showSession', v))
        self.notes_toggle.toggled.connect(lambda v: self.toggle_sidebar(self.notes, 'showNotes', v))
        guide = button('Guida', 'header', lambda: Guide(self).exec(), icon='book')
        for b in (self.events_toggle, self.notes_toggle, guide):
            layout.addWidget(b)
        self.language = combo([('it', 'Italiano'), ('en', 'English')], self.set_language)
        select_combo(self.language, i18n.language())
        self.language.setAccessibleName(T('Lingua dell’app'))
        self.appearance = combo([('system', 'Sistema'), ('light', 'Chiara'), ('dark', 'Scura')], self.set_appearance)
        select_combo(self.appearance, self.settings.value('appearance', 'system', str))
        self.appearance.setAccessibleName(T('Tema dell’app'))
        self.appearance.setToolTip(T('Chiara, Scura oppure Sistema per seguire automaticamente l’aspetto di macOS'))
        for text, picker in (('Lingua', self.language), ('Tema', self.appearance)):
            picker.setMinimumWidth(96)
            layout.addSpacing(6)
            layout.addWidget(label(text, wrap=False))
            layout.addWidget(picker)
        layout.addSpacing(6)
        stop = button('STOP', 'danger', self.stop, 'Arresta subito ogni movimento (Esc)', icon='stop')
        layout.addWidget(stop)
        return header

    def _pages(self):
        from .assistant import CompanionPanel
        from .diagnostics import CameraPanel, ROSPanel, TelemetryPanel
        from .operator import ConnectionPanel, FirmwareEditorPanel, FirmwarePanel, LimitsPanel, MotionPanel, SequencePanel
        from .studio import ArmPanel, CartesianPanel, MoveJPreviewPanel, ProgramPanel, StudioSetupPanel
        from .widgets import Card
        m = self.m
        p = self.panels
        p['connection'] = ConnectionPanel(m, self)
        p['firmware'] = FirmwarePanel(m, self)
        p['firmware_editor'] = FirmwareEditorPanel(m, self)
        p['setup'] = StudioSetupPanel(m, self)
        p['limits'] = LimitsPanel(m, self)
        p['motion'] = MotionPanel(m, self)
        p['sequence'] = SequencePanel(m, self)
        arm_card = Card('Braccio 3D · target virtuale', resizable=False)
        arm_card.arm = ArmPanel(m, self)
        arm_card.add(arm_card.arm)
        arm_card.refresh = arm_card.arm.refresh
        studio_panels = [arm_card, CartesianPanel(m, self), MoveJPreviewPanel(m, self), StudioSetupPanel(m, self), ProgramPanel(m, self),
                         SequencePanel(m, self)]
        self.camera = CameraPanel(m, self)
        self.pages = {
            'operator': Page(m, [p['connection'], p['firmware'], p['firmware_editor'], p['setup'], p['limits'], p['motion'], p['sequence']]),
            'studio': Page(m, studio_panels),
            'diagnostics': Page(m, [TelemetryPanel(m, self), ROSPanel(m, self), self.camera]),
            'assistant': Page(m, [CompanionPanel(m, self)]),
        }
        for key, _ in WORKSPACES:
            self.stack.addWidget(self.pages[key])

    def _menus(self):
        bar = self.menuBar()
        view = bar.addMenu(T('Vista'))
        a = QAction(T('Attività del robot'), self, checkable=True, shortcut=QKeySequence('Ctrl+B'))
        a.toggled.connect(self.events_toggle.setChecked)
        self.events_toggle.toggled.connect(a.setChecked)
        view.addAction(a)
        b = QAction(T('Note operatore'), self, checkable=True, shortcut=QKeySequence('Ctrl+Alt+B'))
        b.toggled.connect(self.notes_toggle.setChecked)
        self.notes_toggle.toggled.connect(b.setChecked)
        view.addAction(b)
        robot = bar.addMenu(T('Robot'))
        minus = QAction(T('Giunto selezionato −'), self, shortcut=QKeySequence('Alt+Left'))
        plus = QAction(T('Giunto selezionato +'), self, shortcut=QKeySequence('Alt+Right'))
        minus.triggered.connect(lambda: self.keyboard_jog(-1))
        plus.triggered.connect(lambda: self.keyboard_jog(1))
        stop = QAction(T('STOP'), self)
        stop.triggered.connect(self.stop)
        robot.addActions([minus, plus, stop])
        look = bar.addMenu(T('Aspetto'))
        group = QActionGroup(self)
        for value, text in (('system', 'Sistema'), ('light', 'Chiara'), ('dark', 'Scura')):
            action = QAction(T(text), self, checkable=True)
            action.setChecked(value == self.settings.value('appearance', 'system', str))
            action.triggered.connect(lambda _c=False, v=value: (select_combo(self.appearance, v), self.set_appearance(v)))
            group.addAction(action)
            look.addAction(action)
        helpm = bar.addMenu(T('Aiuto'))
        guide = QAction(T('Guida'), self)
        guide.triggered.connect(lambda: Guide(self).exec())
        helpm.addAction(guide)
        about = QAction('Robot Console ' + __version__, self)
        about.setEnabled(False)
        helpm.addAction(about)

    # Behaviour -------------------------------------------------------------------------------------
    def toggle_sidebar(self, widget, key, visible):
        widget.setVisible(visible)
        self.settings.setValue(key, visible)

    def set_workspace(self, value, save=True):
        index = [k for k, _ in WORKSPACES].index(value) if value in dict(WORKSPACES) else 0
        self.stack.setCurrentIndex(index)
        self.m.keyboard_enabled = value == 'operator'
        if value != 'diagnostics' and self.camera.running:
            self.camera.stop()
        if save:
            self.settings.setValue('workspace', value)
        self.refresh()

    def set_language(self, code):
        if code == i18n.language():
            return
        self.settings.setValue('language', code)
        if confirm(self, 'Cambia lingua', 'La nuova lingua si applica al riavvio della finestra. Il controllo e il robot restano attivi.', 'Riavvia finestra'):
            self.rebuild_window()
        else:
            select_combo(self.language, i18n.language())
            self.settings.setValue('language', i18n.language())

    def rebuild_window(self):
        """Recreate the widgets in the new language; the controller process keeps running."""
        app = QApplication.instance()
        i18n.set_language(self.settings.value('language', 'it', str))
        self.settings.setValue('geometry', self.saveGeometry())
        self.allow_quit = True
        for signal, slot in ((self.m.updated, self.refresh), (self.m.message_changed, self._message), (self.m.quit_ready, self.force_quit)):
            signal.disconnect(slot)
        if self.camera.running:
            self.camera.stop()
        replacement = MainWindow(self.m, self.settings)
        app.main_window = replacement
        replacement.show()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.close()

    def set_appearance(self, value):
        self.settings.setValue('appearance', value)
        theme.apply(QApplication.instance(), value)
        retint(self)
        self.refresh()

    def stop(self):
        self.m.stop()

    def keyboard_jog(self, sign):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox, QComboBox)) or QApplication.activeModalWidget():
            return
        self.m.keyboard_jog(sign)

    def _message(self, _text):
        self.refresh_banner()

    def refresh_banner(self):
        m = self.m
        parts = [T(x) for x in (m.message, m.state.get('error', '')) if x]
        self.banner.setVisible(bool(parts))
        self.banner_text.setText(' · '.join(parts))

    def refresh(self):
        m, s = self.m, self.m.state
        status = m.connection_status()
        self.status_chip.set(status, theme.FIXED['header_secondary'] if not s.get('connected') else
                             (theme.FIXED['lime'] if status == 'Pronto' else theme.FIXED['amber']))
        demo = s.get('mode') == 'demo'
        self.mode_chip.set('ANTEPRIMA' if demo else 'ROBOT REALE', theme.FIXED['lime'] if demo else theme.FIXED['amber'], filled=not demo)
        self.refresh_banner()
        self.approval.refresh()
        if self.session.isVisible():
            self.session.refresh()
        self.stack.currentWidget().refresh()
        self.check_return_to_quit()

    # Quit flow ---------------------------------------------------------------------------------------
    def closeEvent(self, event):
        if self.allow_quit:
            self.settings.setValue('geometry', self.saveGeometry())
            event.accept()
            return
        event.ignore()
        m = self.m
        if m.firmware.get('busy'):
            m.set_message(T('Attendi la conclusione dell’operazione firmware prima di chiudere.'))
            return
        if not m.state.get('connected') or (m.idle and m.zero):
            self.force_quit()
            return
        options = []
        if m.idle and m.state.get('home'):
            options.append(('home', 'Torna a HOME', False))
        if m.state.get('playing'):
            options.append(('cycle', 'Completa ciclo e HOME', False))
        options.append(('stop', 'STOP ed esci', True))
        answer = choose(self, 'Chiudi Robot Console',
                        'Il robot non risulta fermo a HOME. Il ritorno è disponibile solo da fermo con riferimento valido. STOP interrompe gli impulsi mantenendo la tenuta.',
                        options, 'Resta nell’app')
        if answer == 'home':
            m.returning_to_quit, m.return_request_accepted = True, False
            m.send('home')
        elif answer == 'cycle':
            m.returning_to_quit, m.return_request_accepted = True, True
            m.send('end_cycle', {'return_home': True})
        elif answer == 'stop':
            self.force_quit()

    def check_return_to_quit(self):
        m = self.m
        if m.returning_to_quit and m.return_request_accepted and m.idle:
            m.returning_to_quit = False
            if m.zero:
                if confirm(self, 'Verifica HOME', 'Ritorno completato nel conteggio impulsi. Verifica visivamente la posizione del robot.',
                           'HOME verificata: esci', cancel='Resta nell’app'):
                    self.force_quit()
            else:
                m.set_message(T('Ritorno interrotto. Verifica la posizione del robot.'))

    def force_quit(self):
        if self.camera.running:
            self.camera.stop()
        self.allow_quit = True
        self.settings.setValue('geometry', self.saveGeometry())
        self.m.shutdown()
        # exit(), not quit(): on macOS quit() goes through [NSApp terminate:], which calls exit() while
        # PySide still owns the widgets and crashes in their teardown (closing from ⌘Q or the Dock).
        QApplication.instance().exit(0)


def _padded(widget):
    holder = QWidget()
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(16, 10, 16, 0)
    layout.addWidget(widget)
    holder.setVisible(False)
    widget.visibility_holder = holder
    original = widget.setVisible

    def set_visible(value):
        original(value)
        holder.setVisible(value)
    widget.setVisible = set_visible
    return holder


class ApprovalBanner(QFrame):
    """Python API request waiting for the operator on the real robot."""

    def __init__(self, m):
        super().__init__()
        self.m = m
        self.setObjectName('Banner')
        self.name = label('', 'section')
        self.detail = caption()
        self.approve = button('Approva ed esegui', 'prominent', lambda: self.answer(True))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(label('✋'))
        layout.addLayout(_column(label('Richiesta Python · conferma sul robot reale', 'section'), self.name, self.detail,
                                 caption('Controlla il piano in Studio prima di approvare. La conferma vale solo per questa esecuzione.')), 1)
        layout.addWidget(button('Rifiuta richiesta', None, lambda: self.answer(False)))
        layout.addWidget(self.approve)

    def answer(self, value):
        request = (self.m.local_api or {}).get('pending')
        if request:
            self.m.send('api_approve', dict(id=request['id'], confirmed=value))

    def refresh(self):
        request = (self.m.local_api or {}).get('pending')
        self.setVisible(bool(request))
        if request:
            self.name.setText(request.get('name', ''))
            self.detail.setText(F('Piano %@ · %.1f s stimati · %lld rami verificati', request.get('plan_id', '')[:12], request.get('duration', 0),
                                  request.get('branches', 1)))
            self.approve.setEnabled(self.m.idle and not self.m.speed_edits)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog='robot_console', description='Robot Console · DOC 5-DOF arm')
    parser.add_argument('--no-hardware', action='store_true', help='preview only: the controller refuses to open the USB port')
    parser.add_argument('--data', metavar='FOLDER', help='use this data folder instead of the default one')
    options, rest = parser.parse_known_args((argv if argv is not None else sys.argv)[1:])
    environment = {}
    if options.no_hardware:
        environment['DOC_REGIA_NO_HARDWARE'] = '1'
    if options.data:
        environment['DOC_REGIA_DATA'] = str(Path(options.data).expanduser().resolve())
    from .viewport3d import configure_graphics
    configure_graphics()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([sys.argv[0]] + rest)
    app.setApplicationName('Robot Console')
    app.setOrganizationName('DOC')
    app.setApplicationVersion(__version__)
    icon = ROOT / 'qtui' / 'icons' / 'app.png'
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    settings = QSettings('DOC', 'Robot Console')
    i18n.set_language(settings.value('language', 'it', str))
    theme.apply(app, settings.value('appearance', 'system', str))
    try:
        app.styleHints().colorSchemeChanged.connect(lambda _s: settings.value('appearance', 'system', str) == 'system' and
                                                    (theme.apply(app, 'system'), app.main_window.refresh()))
    except AttributeError:
        pass
    model = AppModel(environment)
    app.main_window = MainWindow(model, settings)
    app.main_window.show()
    model.start()
    app.aboutToQuit.connect(model.shutdown)
    return app.exec()
