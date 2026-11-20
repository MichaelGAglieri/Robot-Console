# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Desktop app end to end: real controller process in preview mode, offscreen Qt window."""
import os, sys, time, unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
except ImportError:  # the desktop app is optional for the controller tests
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class QtAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qtui import app as appmod, i18n, theme, widgets
        from qtui.viewport3d import configure_graphics
        configure_graphics()
        cls.app = QApplication.instance() or QApplication([sys.argv[0]])
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, os.environ.get('DOC_REGIA_DATA', '.'))
        i18n.set_language('it')
        theme.apply(cls.app, 'dark')
        # Dialogs would block an unattended run: accept every confirmation.
        accept = lambda *a, **k: True
        import qtui.operator, qtui.studio
        for module in (widgets, appmod, qtui.operator, qtui.studio):
            module.confirm = accept
        cls.settings = QSettings('DOC', 'Robot Console Tests')
        cls.model = appmod.AppModel({'DOC_REGIA_NO_HARDWARE': '1'})
        cls.window = appmod.MainWindow(cls.model, cls.settings)
        cls.window.show()
        cls.model.start()

    @classmethod
    def tearDownClass(cls):
        cls.window.allow_quit = True
        cls.model.shutdown()
        cls.window.close()

    def wait(self, condition, seconds=20):
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(.02)
        return False

    def test_preview_session(self):
        m, w = self.model, self.window
        self.assertTrue(self.wait(lambda: m.studio is not None), 'controller did not answer')
        m.send('connect', dict(mode='demo', port=''))
        self.assertTrue(self.wait(lambda: m.state.get('connected')))
        m.send('home_set')
        self.assertTrue(self.wait(lambda: m.state.get('home')))
        limits = w.panels['limits']
        limits.set_preset(90)
        limits.apply()
        self.assertTrue(self.wait(lambda: m.state['limits'][0] == [-90, 90]))
        w.panels['motion'].select_step(5)
        m.jog(0, 1)
        self.assertTrue(self.wait(lambda: abs(m.state['pos'][0] - 5) < 1e-6 and m.idle))
        w.panels['sequence'].record_pose()
        self.assertTrue(self.wait(lambda: len(m.state['sequence']) == 1))
        for key in ('studio', 'diagnostics', 'assistant', 'operator'):
            w.workspace._clicked(key)
            self.app.processEvents()
        program = next(p for p in w.pages['studio'].panels if type(p).__name__ == 'ProgramPanel')
        from qtui.widgets import select_combo
        select_combo(program.kind, 'movej')
        select_combo(program.destination, 'home')
        program.add_block()
        self.assertTrue(self.wait(lambda: len(m.studio.get('blocks') or []) == 1))
        program.replan({})
        self.assertTrue(self.wait(lambda: (m.studio.get('movej_preview') or {}).get('valid')))
        self.assertEqual(m.message, '')

    def test_translation_formats(self):
        from qtui.i18n import F, set_language
        self.assertEqual(F('Durata stimata %.1f s · %lld istruzioni · %lld tratti', 3.25, 4, 2), 'Durata stimata 3.2 s · 4 istruzioni · 2 tratti')
        set_language('en')
        try:
            self.assertIn('Estimated duration', F('Durata stimata %.1f s · %lld istruzioni · %lld tratti', 3.25, 4, 2))
        finally:
            set_language('it')


if __name__ == '__main__':
    unittest.main()
