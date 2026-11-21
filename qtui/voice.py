# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Voice motion commands: recognised or typed, summarised aloud, confirmed with “sì confermo”.

Never sent to an LLM. The confirmation listens only after the summary has been spoken,
so the question cannot confirm itself; it expires after 30 seconds.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout
from .i18n import T
from .speech import Dictation, Speaker
from .widgets import Disclosure, button, caption, checkbox, label, line, row

CANCEL = ('annulla', 'cancel', 'no')


class VoiceMotionControls(Disclosure):
    def __init__(self, m, window):
        super().__init__('Comandi vocali del robot')
        self.m, self.window = m, window
        self.dictation = Dictation(self)
        self.speaker = Speaker(self)
        self.add(caption('Di’: muovi J2 di 45 gradi; muovi J1 a 45 e J2 a 30; avvia posa 1. A indica la posizione assoluta, di uno spostamento relativo.'))
        self.transcript = line('Comando da riconoscere')
        self.add(self.transcript)
        self.listen_button = button('Parla al robot', None, self.begin)
        self.read_button = button('Leggi e chiedi conferma', None, self.prepare_typed)
        self.add(row(self.listen_button, self.read_button, button('Annulla ascolto', None, self.cancel),
                     button('STOP', 'danger', lambda: (self.cancel(), m.send('stop'))), None))
        self.answer = line('Scrivi «sì confermo» oppure «annulla»')
        self.answer.returnPressed.connect(lambda: self.confirm(self.answer.text()))
        self.answer_button = button('Conferma', 'prominent', lambda: self.confirm(self.answer.text()))
        self.answer_row = self._holder(row(self.answer, self.answer_button))
        self.add(self.answer_row)
        self.continuous = checkbox('Ascolta il prossimo comando a movimento concluso')
        self.continuous.setChecked(True)
        self.stage_label = label('', 'accent')
        self.heard = caption()
        self.summary = label('')
        self.notice = caption()
        self.add(self.continuous, self.stage_label, self.heard, self.summary, self.notice)
        self.add(caption('Trascrizione locale, senza IA. Attendi il riepilogo e rispondi sì confermo. La conferma scade dopo 30 secondi; STOP resta disponibile anche da tastiera (Esc).'))
        self.stage = ''
        self.session = 0
        self.command = None
        self.silence = QTimer(self)
        self.silence.setSingleShot(True)
        self.silence.setInterval(1500)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.on_text = None
        self.dictation.heard.connect(self._heard)
        self.dictation.notice.connect(lambda text: self.notice.setText(T(text)))
        self.silence.timeout.connect(self._silence)
        self.timeout.timeout.connect(self._expired)
        self.last_busy = None
        self.last_home = None

    @staticmethod
    def _holder(layout):
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        w.setLayout(layout)
        return w

    def set_stage(self, text):
        self.stage = text
        self.stage_label.setText(T(text))
        self.refresh()

    def cancel(self):
        self.session += 1
        self.silence.stop()
        self.timeout.stop()
        self.dictation.stop()
        self.speaker.stop()
        self.m.voice_command = None
        self.command = None
        self.on_text = None
        self.heard.setText('')
        self.summary.setText('')
        self.set_stage('')
        self.m.send('voice_cancel')

    def listen(self, callback):
        self.on_text = callback
        if not self.dictation.start():
            self.on_text = None
            return False
        return True

    def _heard(self, text):
        self.heard.setText(text)
        self.silence.start()

    def _silence(self):
        callback, text = self.on_text, self.dictation.text or self.heard.text()
        self.dictation.stop()
        self.on_text = None
        if callback:
            callback(text)

    def _expired(self):
        if self.stage == 'Riepilogo vocale' or self.stage.startswith('Di’'):
            self.cancel()
            self.m.set_message(T('Conferma vocale scaduta. Ripeti il comando.'))
        else:
            self.cancel()

    def begin(self):
        self.cancel()
        self.transcript.setText('')
        self.set_stage('Ascolto comando')
        self.timeout.start(20000)
        session = self.session

        def got(text):
            if session != self.session:
                return
            if text.lower().strip() in CANCEL:
                self.cancel()
                return
            self.transcript.setText(text)
            self.prepare()
        if not self.listen(got):
            self.set_stage('')
            self.timeout.stop()

    def prepare_typed(self):
        self.session += 1
        self.prepare()

    def prepare(self):
        self.timeout.stop()
        self.dictation.stop()
        self.silence.stop()
        session = self.session
        text = self.transcript.text().strip()
        self.m.voice_command = None

        def done(ok, _reply):
            if session != self.session:
                return
            command = self.m.voice_command
            if not ok or not command or command.get('text') != text:
                self.set_stage('')
                return
            self.command = command
            self.summary.setText(command.get('summary', ''))
            self.set_stage('Riepilogo vocale')
            self.timeout.start(29000)
            self.answer.setText('')

            def spoken():
                self.speaker.finished.disconnect(spoken)
                if session != self.session:
                    return
                # A fresh recognizer starts only after synthesis ends.
                QTimer.singleShot(500, lambda: self._ask(session))
            self.speaker.finished.connect(spoken)
            self.speaker.speak(command.get('summary', ''))
        self.m.send('voice_prepare', dict(text=text), done)

    def _ask(self, session):
        if session != self.session:
            return
        self.set_stage('Di’ sì confermo oppure annulla')
        self.heard.setText('')
        self.answer.setFocus()
        self.listen(lambda answer: self.confirm(answer))

    def confirm(self, answer):
        command = self.command
        if not command or not (self.stage == 'Riepilogo vocale' or self.stage.startswith('Di’')):
            return
        session = self.session
        self.timeout.stop()
        self.dictation.stop()
        self.m.voice_command = None
        self.command = None
        normalized = answer.lower().strip()
        self.set_stage('Movimento vocale in corso')

        def done(ok, _reply):
            if session != self.session:
                return
            if not ok or normalized in CANCEL:
                self.set_stage('')
            else:
                self.next_command()
        self.m.send('voice_execute', dict(token=command['token'], confirmation=answer), done)

    def next_command(self):
        if self.stage != 'Movimento vocale in corso' or not self.m.idle:
            return
        s = self.m.state
        if self.continuous.isChecked() and s.get('home') and not s.get('error') and not Dictation.unavailable_reason():
            self.begin()
        else:
            self.set_stage('')

    def refresh(self):
        m, s = self.m, self.m.state
        busy, home = s.get('busy'), s.get('home')
        if busy != self.last_busy:
            self.last_busy = busy
            self.next_command()
        if home != self.last_home:
            if self.last_home and not home and self.stage:
                self.cancel()
            self.last_home = home
        free = bool(home and m.idle and not self.stage)
        self.listen_button.setEnabled(free)
        self.read_button.setEnabled(free and bool(self.transcript.text().strip()))
        self.transcript.setEnabled(not self.stage)
        self.answer_row.setVisible(self.stage == 'Riepilogo vocale' or self.stage.startswith('Di’'))
        if not self.notice.text():
            reason = Dictation.unavailable_reason()
            if reason:
                self.notice.setText(T(reason))
