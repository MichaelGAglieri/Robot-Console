# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Assistant: local chat over the robot state and diary, optional offline LLM through Ollama."""
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from .i18n import T
from .speech import Dictation, Speaker, spoken_text
from .widgets import Card, Disclosure, button, caption, checkbox, clear_layout, combo, label, line, row, set_combo_items, well
from platform_support import data_folder

DOWNLOAD = {'darwin': 'https://ollama.com/download/mac', 'win32': 'https://ollama.com/download/windows'}.get(sys.platform, 'https://ollama.com/download/linux')


def link(text, url):
    w = label('<a href="%s">%s</a>' % (url, T(text)))
    w.setOpenExternalLinks(True)
    return w


class CompanionPanel(Card):
    def __init__(self, m, window):
        super().__init__('Assistente · memoria locale')
        self.m, self.window = m, window
        self.use_llm = False
        self.add(caption('Chat e voce consultano lo stato e il diario. Per muovere il robot usa i controlli manuali.'))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(240)
        holder = QWidget()
        self.messages = QVBoxLayout(holder)
        self.messages.setSpacing(12)
        self.messages.addStretch(1)
        self.scroll.setWidget(holder)
        self.add(self.scroll)
        bar = self.scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _a, b: bar.setValue(b))
        self.draft = line('Scrivi una domanda o Ricorda: …')
        self.draft.returnPressed.connect(self.ask)
        self.draft.textChanged.connect(lambda _t: self.refresh())
        self.send_button = button('Invia', 'prominent', self.ask)
        self.dictation = Dictation(self)
        self.dictation.heard.connect(self.draft.setText)
        self.dictation.notice.connect(lambda t: self.voice_note.setText(T(t)))
        self.dictation.stopped.connect(lambda: self.refresh())
        self.speaker = Speaker(self)
        self.talk = button('Parla', None, self.toggle_dictation)
        self.read = button('Leggi risposta', None, self.speak)
        self.add(row(self.draft, self.send_button, self.talk, self.read, button('Silenzio', None, self.speaker.stop)))
        self.voice_note = caption()
        self.add(self.voice_note)
        self.llm = checkbox('Conversazione libera · IA offline con Ollama', self._llm)
        self.add(self.llm)
        box = QVBoxLayout()
        box.setSpacing(10)
        self.dot = label('●')
        self.status = label('', 'accent')
        self.refresh_button = button('Aggiorna', None, lambda: m.send('ollama_refresh'))
        self.stop_button = button('Ferma IA e libera memoria', None, self.stop_llm,
                                  'Scarica il modello selezionato. Se il servizio è stato avviato da questa app, lo arresta.')
        box.addLayout(row(self.dot, self.status, None, self.refresh_button, self.stop_button))
        self.details = caption()
        box.addWidget(self.details)
        self.models = combo([('', 'Scegli un modello')], lambda v: v and m.send('ollama_select', dict(model=v)))
        self.load = button('Avvia e carica modello', None, lambda: m.send('ollama_start'))
        self.models_row = QWidget()
        self.models_row.setLayout(row(label('Modello locale'), self.models, self.load, None))
        box.addWidget(self.models_row)
        self.start_button = button('Avvia Ollama e cerca modelli', None, lambda: m.send('ollama_start'))
        box.addLayout(row(self.start_button, None))
        self.loaded = caption()
        self.error = label('', 'warning', selectable=True)
        self.download = link('Scarica Ollama dal sito ufficiale', DOWNLOAD)
        self.no_models = caption('Installa prima un modello locale in Ollama, poi premi Aggiorna. Il primo download richiede Internet; dopo puoi lavorare offline.')
        self.library = link('Modelli sul sito ufficiale', 'https://ollama.com/library')
        for w in (self.loaded, self.error, self.download, self.no_models, self.library):
            box.addWidget(w)
        box.addWidget(caption('All’invio di una domanda con IA attiva avvio Ollama e carico il modello scelto. Uso solo modelli già presenti sul computer; nessun download automatico.'))
        box.addWidget(caption('Ferma IA scarica il modello selezionato dalla memoria e disattiva la conversazione libera. Il modello resta su disco. Un servizio Ollama già aperto da altre app rimane avviato. Il comando è disponibile al termine della risposta o del caricamento.', small=True))
        self.add(well(box))
        diary = Disclosure('Diario persistente · ultimi 30 eventi')
        self.diary = QVBoxLayout()
        diary.add(self.diary)
        diary.add(caption(T('Memoria conservata in ') + str(data_folder() / 'memoria.sqlite3') + '. ' +
                          T('Le posizioni da impulsi non sono misure fisiche.'), small=True))
        self.add(diary)
        self.chat_key = self.diary_key = None

    def _llm(self, enabled):
        self.use_llm = enabled
        if enabled:
            self.m.send('ollama_start')

    def stop_llm(self):
        self.use_llm = False
        self.llm.setChecked(False)
        self.m.send('ollama_stop')

    def ask(self):
        text = self.draft.text().strip()
        if not text or self.m.assistant_busy:
            return
        self.dictation.stop()
        self.m.send('chat', dict(text=text, llm=self.use_llm))
        self.draft.setText('')

    def toggle_dictation(self):
        if self.dictation.listening:
            self.dictation.stop()
        else:
            self.speaker.stop()
            self.dictation.start()
        self.refresh()

    def speak(self):
        self.dictation.stop()
        answer = next((e['text'] for e in reversed(self.m.chat) if e.get('kind') == 'assistant'), '')
        text = spoken_text(answer)
        if text:
            if not self.speaker.available():
                self.voice_note.setText(T('Sintesi vocale non disponibile su questo sistema.'))
            self.speaker.speak(text)

    def rebuild_chat(self):
        clear_layout(self.messages)
        if not self.m.chat:
            self.messages.addWidget(caption('Chiedi: Qual è lo stato? · Cosa è successo? · Quali pose ho salvato?'))
        for entry in self.m.chat:
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(label('Tu' if entry.get('kind') == 'user' else 'Assistente', 'accent'))
            box.addWidget(label(entry.get('text', ''), selectable=True))
            self.messages.addWidget(well(box, 'Well', 10))
        self.messages.addStretch(1)

    def refresh(self):
        m, o = self.m, self.m.ollama
        key = repr(m.chat)
        if key != self.chat_key:
            self.chat_key = key
            self.rebuild_chat()
        busy = m.assistant_busy
        self.send_button.setText(T('Rispondo…' if busy else 'Invia'))
        self.send_button.setEnabled(not busy and bool(self.draft.text().strip()))
        self.talk.setText(T('Ferma dettatura' if self.dictation.listening else 'Parla'))
        self.read.setEnabled(any(e.get('kind') == 'assistant' for e in m.chat))
        self.dot.setStyleSheet('color: %s;' % ('#A3EA2F' if o.get('running') else 'gray'))
        self.status.setText(T(o.get('status', '')) + ('  …' if o.get('busy') else ''))
        self.stop_button.setEnabled(bool(o.get('running') and not o.get('busy') and not busy))
        details = [T('Installazione: ') + T('presente' if o.get('installed') else 'non rilevata'),
                   T('Servizio: ') + T('avviato' if o.get('running') else 'spento')]
        if o.get('version'):
            details.append('v' + o['version'])
        self.details.setText('   '.join(details))
        models = o.get('models') or []
        self.models_row.setVisible(bool(models))
        names = [x['name'] for x in models]
        set_combo_items(self.models, [('', 'Scegli un modello')] + [(x['name'], '%s · %.1f GB su disco' % (x['name'], x.get('size', 0) / 1e9)) for x in models],
                        o.get('selected') if o.get('selected') in names else '')
        self.models.setEnabled(not o.get('busy') and not busy)
        self.load.setEnabled(not o.get('busy') and not busy)
        self.start_button.setVisible(not models and bool(o.get('installed')))
        self.start_button.setEnabled(not o.get('busy'))
        self.loaded.setText(T('Caricati in memoria: ') + (', '.join(o.get('loaded') or []) or T('nessuno')))
        self.error.setVisible(bool(o.get('error')))
        self.error.setText(T(o.get('error') or ''))
        self.download.setVisible(not o.get('installed'))
        empty = bool(o.get('installed') and o.get('running') and not models)
        self.no_models.setVisible(empty)
        self.library.setVisible(empty)
        key = repr(m.diary)
        if key != self.diary_key:
            self.diary_key = key
            clear_layout(self.diary)
            for entry in reversed(m.diary or []):
                self.diary.addWidget(caption(entry.get('time', '') + ' · ' + entry.get('source', ''), small=True))
                self.diary.addWidget(label(entry.get('text', ''), 'caption', selectable=True))
