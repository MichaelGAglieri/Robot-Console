# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local speech: text to speech through QtTextToSpeech, optional offline dictation through Vosk.

Audio never leaves the computer. Dictation needs the optional packages `vosk` and
`sounddevice` plus a Vosk model folder (for example vosk-model-small-it-0.22) placed in
<data folder>/speech/<language> or named by ROBOT_CONSOLE_VOSK_MODEL. Without them the
console keeps the typed command field, which goes through the same confirmation.
"""
import json, os, re
from pathlib import Path
from PySide6.QtCore import QLocale, QObject, Signal
from .i18n import language

ATTRIBUTION = re.compile(r'\A\s*\[(?:Ollama locale|Local Ollama)\s*·[^\]\r\n]*\]\s*')


def spoken_text(answer):
    """Model attribution stays in the chat; only the leading metadata is silent."""
    return ATTRIBUTION.sub('', answer or '').strip()


class Speaker(QObject):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.speaking = False
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech
            self.engine = QTextToSpeech(self)
            self.engine.stateChanged.connect(self._state)
        except Exception:  # module missing or no speech backend on this system
            self.engine = None

    def available(self):
        return self.engine is not None

    def _state(self, state):
        from PySide6.QtTextToSpeech import QTextToSpeech
        if state == QTextToSpeech.State.Ready and self.speaking:
            self.speaking = False
            self.finished.emit()

    def speak(self, text):
        if not self.engine or not text:
            self.finished.emit()
            return
        self.stop()
        wanted = QLocale(QLocale.English if language() == 'en' else QLocale.Italian)
        for locale in self.engine.availableLocales():
            if locale.language() == wanted.language():
                self.engine.setLocale(locale)
                break
        self.speaking = True
        self.engine.say(text)

    def stop(self):
        if self.engine:
            self.speaking = False
            self.engine.stop()


def vosk_model():
    """Folder of the offline recognition model for the current language, or None."""
    explicit = os.environ.get('ROBOT_CONSOLE_VOSK_MODEL')
    if explicit and Path(explicit).is_dir():
        return Path(explicit)
    try:
        from platform_support import data_folder
    except ImportError:
        return None
    root = data_folder() / 'speech' / ('en' if language() == 'en' else 'it')
    if (root / 'am').is_dir() or (root / 'conf').is_dir():
        return root
    if root.is_dir():
        nested = [p for p in root.iterdir() if p.is_dir() and ((p / 'am').is_dir() or (p / 'conf').is_dir())]
        if nested:
            return nested[0]
    return None


class Dictation(QObject):
    """Offline dictation. `heard` carries the running transcript; `stopped` ends a session."""
    heard = Signal(str)
    stopped = Signal()
    notice = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stream = None
        self.recognizer = None
        self.model = None
        self.model_path = None
        self.text = ''

    @staticmethod
    def unavailable_reason():
        try:
            import vosk  # noqa: F401
            import sounddevice  # noqa: F401
        except Exception:
            return 'Dettatura locale non disponibile: installa i pacchetti facoltativi vosk e sounddevice. Puoi scrivere il comando.'
        if vosk_model() is None:
            return 'Dettatura locale: manca il modello Vosk della lingua scelta (vedi Guida). Puoi scrivere il comando.'
        return ''

    @property
    def listening(self):
        return self.stream is not None

    def start(self):
        self.stop()
        reason = self.unavailable_reason()
        if reason:
            self.notice.emit(reason)
            return False
        import sounddevice as sd
        import vosk
        path = vosk_model()
        try:
            if self.model is None or self.model_path != path:
                vosk.SetLogLevel(-1)
                self.model, self.model_path = vosk.Model(str(path)), path
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            self.text = ''
            self.stream = sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16', channels=1, callback=self._audio)
            self.stream.start()
        except Exception as error:  # microphone missing or permission refused
            self.stream = None
            self.notice.emit('Microfono non disponibile: ' + str(error))
            return False
        self.notice.emit('Ti ascolto.')
        return True

    def _audio(self, data, _frames, _time, _status):
        # Audio thread: only signals cross into the interface (queued connections).
        recognizer = self.recognizer
        if recognizer is None:
            return
        if recognizer.AcceptWaveform(bytes(data)):
            final = json.loads(recognizer.Result()).get('text', '')
            if final:
                self.text = (self.text + ' ' + final).strip()
                self.heard.emit(self.text)
        else:
            partial = json.loads(recognizer.PartialResult()).get('partial', '')
            if partial:
                self.heard.emit((self.text + ' ' + partial).strip())

    def stop(self):
        stream, self.stream = self.stream, None
        self.recognizer = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
            self.stopped.emit()
