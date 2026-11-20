# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Industrial palette shared with the macOS app: neutral greys, DOC lime as accent only.

Light-mode text keeps at least 4.8:1 contrast on every background.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

LIGHT = dict(canvas='#E8ECF0', well='#F2F4F7', graphite='#F6F7F9', surface='#FFFFFF', border='#CDD4DC',
             text='#11161B', secondary='#4F5A66', accent='#2B760C', stop='#C62828', warning='#A15C00',
             viewport='#ECEFF2', grid='#B8C0C8')
DARK = dict(canvas='#0B0E10', well='#12161A', graphite='#1C2227', surface='#171C20', border='#2C343B',
            text='#E7EBEE', secondary='#9AA4AE', accent='#A6F43C', stop='#FF5A52', warning='#FFB020',
            viewport='#0E1114', grid='#3A434B')
ICONS = Path(__file__).resolve().parent / 'icons'
FIXED = dict(lime='#A3EA2F', ink='#0B0F0B', header='#14191E', header_text='#EEF2F5', header_secondary='#9AA5B0',
             header_control='#232A31', amber='#FFB020', control='#2B760C')

_current = dict(DARK, **FIXED)
_dark = True


def resolve(appearance):
    """'system', 'light' or 'dark' -> True when dark colours should be used."""
    if appearance == 'light':
        return False
    if appearance == 'dark':
        return True
    hints = QGuiApplication.styleHints()
    try:
        return hints.colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return QGuiApplication.palette().color(QPalette.Window).lightness() < 128


def color(name):
    return QColor(_current[name])


def is_dark():
    return _dark


def apply(app, appearance):
    global _current, _dark
    _dark = resolve(appearance)
    _current = dict(DARK if _dark else LIGHT, **FIXED)
    c = _current
    palette = QPalette()
    for role, key in ((QPalette.Window, 'canvas'), (QPalette.Base, 'well'), (QPalette.AlternateBase, 'surface'),
                      (QPalette.Button, 'surface'), (QPalette.Text, 'text'), (QPalette.WindowText, 'text'),
                      (QPalette.ButtonText, 'text'), (QPalette.ToolTipBase, 'surface'), (QPalette.ToolTipText, 'text'),
                      (QPalette.PlaceholderText, 'secondary')):
        palette.setColor(role, QColor(c[key]))
    palette.setColor(QPalette.Highlight, QColor(c['control']))
    palette.setColor(QPalette.HighlightedText, QColor('#FFFFFF'))
    palette.setColor(QPalette.Link, QColor(c['accent']))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(c, _dark))


def stylesheet(c, dark):
    small = 11 if dark else 12
    check = (ICONS / 'check.svg').as_posix()
    caption = 12 if dark else 13
    weight = 400 if dark else 500
    return f"""
* {{ font-size: 13px; }}
QWidget {{ color: {c['text']}; }}
QMainWindow, #Canvas, QScrollArea#Content > QWidget > QWidget {{ background: {c['canvas']}; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}

#Header {{ background: {c['header']}; }}
#Header QLabel {{ color: {c['header_text']}; }}
#HeaderRule {{ background: {c['lime']}; }}
#Brand {{ font-size: 14px; font-weight: 800; letter-spacing: 2.4px; }}
#BrandMark {{ background: {c['lime']}; border-radius: 7px; color: {c['ink']}; font-weight: 900; }}
#Workspace {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}

#Sidebar {{ background: {c['graphite']}; }}
#SidebarTitle {{ font-size: 12px; font-weight: 700; letter-spacing: 1px; }}

#Card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#CardTitle {{ font-size: 12px; font-weight: 700; letter-spacing: 1.2px; }}
#CardBar {{ background: {c['lime']}; border-radius: 1px; }}
#CardRule {{ background: {c['border']}; }}
#Well {{ background: {c['well']}; border-radius: 10px; }}
#WellActive {{ background: {c['well']}; border-radius: 12px; border: 1px solid {c['lime']}; }}
#WellPlain {{ background: transparent; border-radius: 10px; }}
#WellIdle {{ background: {c['well']}; border-radius: 12px; border: 1px solid {c['border']}; }}

QLabel[role="caption"] {{ font-size: {caption}px; font-weight: {weight}; color: {c['secondary']}; }}
QLabel[role="small"] {{ font-size: {small}px; color: {c['secondary']}; }}
QLabel[role="mono"] {{ font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; font-size: {small}px; }}
QLabel[role="accent"] {{ color: {c['accent']}; font-weight: 600; }}
QLabel[role="warning"] {{ color: {c['warning']}; }}
QLabel[role="stop"] {{ color: {c['stop']}; }}
QLabel[role="headline"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="title"] {{ font-size: 24px; font-weight: 600; }}
QLabel[role="value"] {{ font-size: 23px; font-weight: 600; color: {c['accent']}; }}
QLabel[role="section"] {{ font-weight: 600; }}

QPushButton {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 7px;
  padding: 6px 13px; font-weight: 600; }}
QPushButton:hover {{ border-color: {c['secondary']}; }}
QPushButton:pressed {{ background: {c['well']}; }}
QPushButton:disabled {{ color: {c['secondary']}; border-color: {c['border']}; }}
QPushButton[kind="prominent"] {{ background: {c['lime']}; color: {c['ink']}; border: 1px solid rgba(0,0,0,0.18); }}
QPushButton[kind="prominent"]:disabled {{ background: rgba(163,234,47,0.40); color: rgba(11,15,11,0.55); }}
QPushButton[kind="danger"] {{ background: {c['stop']}; color: white; border: 1px solid {c['stop']}; }}
QPushButton[kind="danger"]:disabled {{ background: rgba(198,40,40,0.40); }}
QPushButton[kind="compact"] {{ padding: 6px 2px; }}
QPushButton[kind="compact"]:checked {{ background: {c['lime']}; color: {c['ink']}; }}
QPushButton[kind="header"] {{ background: {c['header_control']}; color: {c['header_text']};
  border: 1px solid rgba(255,255,255,0.10); padding: 5px 11px; }}
QPushButton[kind="header"]:checked {{ border-color: {c['lime']}; }}
QPushButton[kind="segment"] {{ background: transparent; border: none; border-radius: 6px; padding: 4px 18px; font-weight: 500; }}
QPushButton[kind="segment"]:checked {{ background: {c['control']}; color: white; }}
#Segments {{ background: {c['well']}; border-radius: 7px; }}
QPushButton[kind="disclosure"] {{ background: transparent; border: none; text-align: left; padding: 4px 0; font-weight: 500; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{ background: {c['well']}; border: 1px solid {c['border']};
  border-radius: 6px; padding: 4px 6px; selection-background-color: {c['control']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit[invalid="true"] {{ border-color: {c['stop']}; }}
QComboBox {{ background: {c['well']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 4px 8px; color: {c['accent']}; }}
QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']}; selection-background-color: {c['control']}; }}
#Header QComboBox {{ background: {c['header_control']}; color: {c['header_text']}; border: 1px solid rgba(255,255,255,0.10); }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; border: 1px solid {c['border']}; background: {c['well']}; }}
QCheckBox::indicator:checked {{ background: {c['lime']}; border-color: {c['lime']}; image: url({check}); }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['surface']}; border: 1px solid {c['secondary']}; width: 16px; height: 16px;
  margin: -7px 0; border-radius: 8px; }}
QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 30px; }}
#ProgramRow {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
#ProgramRow[state="structure"] {{ background: {c['well']}; }}
#ProgramRow[state="selected"] {{ border: 2px solid {c['accent']}; }}
#ProgramRow[state="active"] {{ background: rgba(163,234,47,0.16); border: 2px solid {c['accent']}; }}
#ProgramRow[state="problem"] {{ border: 2px solid {c['stop']}; }}
#Banner {{ background: rgba(255,176,32,0.10); border: 1px solid rgba(255,176,32,0.35); border-radius: 8px; }}
#Banner QLabel {{ color: {c['warning']}; }}
QDialog {{ background: {c['surface']}; }}
QMessageBox {{ background: {c['surface']}; }}
QTabBar::tab {{ padding: 6px 14px; }}
"""
