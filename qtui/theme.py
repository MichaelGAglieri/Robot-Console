# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Industrial palette shared with the macOS app: neutral greys, DOC lime as accent only.

Light-mode text keeps at least 4.8:1 contrast on every background.
"""
import tempfile
from pathlib import Path
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap

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


# Icons ---------------------------------------------------------------------------------------------
# Line icons drawn for this app in qtui/icons (stroke="currentColor"), tinted on demand.
_TINTED = Path(tempfile.gettempdir()) / 'robot-console-icons'


def svg(name, tint):
    """SVG source of an icon with currentColor replaced by a palette name or a colour."""
    value = QColor(_current.get(tint, tint)).name()
    return (ICONS / (name + '.svg')).read_text(encoding='utf-8').replace('currentColor', value)


def icon(name, tint='text', size=16):
    """QIcon rendered sharp at 1x, 2x and 3x."""
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(QByteArray(svg(name, tint).encode()))
    result = QIcon()
    for scale in (1, 2, 3):
        pixmap = QPixmap(size * scale, size * scale)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        result.addPixmap(pixmap)
    return result


def icon_file(name, tint):
    """Tinted copy on disk, for style sheets (url(...))."""
    _TINTED.mkdir(exist_ok=True)
    value = QColor(_current.get(tint, tint)).name()[1:]
    target = _TINTED / ('%s-%s.svg' % (name, value))
    if not target.exists():
        target.write_text(svg(name, tint), encoding='utf-8')
    return target.as_posix()


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
    updown = icon_file('updown', 'accent')
    updown_header = icon_file('updown', 'header_text')
    updown_plain = icon_file('updown', 'secondary')
    chevron_menu = icon_file('chevron-down', 'secondary')
    # macOS menu pickers: tinted capsule, accent text, up/down chevrons.
    picker = 'rgba(166,244,60,0.10)' if dark else 'rgba(43,118,12,0.08)'
    picker_hover = 'rgba(166,244,60,0.17)' if dark else 'rgba(43,118,12,0.14)'
    handle = 'rgba(154,164,174,0.45)' if dark else 'rgba(79,90,102,0.40)'
    field = 'rgba(255,255,255,0.035)' if dark else '#FFFFFF'
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
#BrandMark {{ background: {c['lime']}; border-radius: 7px; }}
#HeaderSeparator {{ background: rgba(255,255,255,0.12); }}
#Workspace {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
#WorkspaceLabel {{ font-size: 13px; }}

#Sidebar {{ background: {c['graphite']}; }}
#Sidebar QScrollArea, #Sidebar QScrollArea > QWidget > QWidget {{ background: transparent; }}
#SidebarTitle {{ font-size: 12px; font-weight: 700; letter-spacing: 1px; }}
#SidebarSection {{ font-size: 11px; font-weight: 600; }}
QPlainTextEdit#Notes {{ background: {c['well']}; border: none; border-radius: 10px; padding: 8px; font-size: 13px; }}

#Card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#Card QScrollArea#CardBody, #Card QScrollArea#CardBody > QWidget > QWidget {{ background: transparent; }}
QScrollArea#Transparent, QScrollArea#Transparent > QWidget > QWidget {{ background: transparent; }}
#CardTitle {{ font-size: 12px; font-weight: 700; letter-spacing: 1.1px; }}
#CardBar {{ background: {c['lime']}; border-radius: 1px; }}
#CardRule {{ background: {c['border']}; }}
QPushButton#CardFit {{ background: transparent; border: none; padding: 0; color: {c['accent']}; font-size: {small}px; font-weight: 400; }}
#Well {{ background: {c['well']}; border-radius: 10px; }}
#WellEvent {{ background: {c['well']}; border-radius: 8px; }}
#WellActive {{ background: {c['well']}; border-radius: 12px; border: 1px solid {c['lime']}; }}
#WellPlain {{ background: transparent; border-radius: 10px; }}
#WellIdle {{ background: {c['well']}; border-radius: 12px; border: 1px solid {c['border']}; }}

QLabel[role="caption"] {{ font-size: {caption}px; font-weight: {weight}; color: {c['secondary']}; }}
QLabel[role="small"] {{ font-size: {small}px; color: {c['secondary']}; }}
QLabel[role="mono"] {{ font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; font-size: {small}px; }}
QLabel[role="monoaccent"] {{ font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; font-size: {caption}px; color: {c['accent']}; }}
QLabel[role="accent"] {{ color: {c['accent']}; font-weight: 600; }}
QLabel[role="guidance"] {{ color: {c['accent']}; font-size: 11px; font-weight: 600; }}
QLabel[role="monostrong"] {{ font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; font-size: 14px; font-weight: 600; }}
QLabel[role="warning"] {{ color: {c['warning']}; font-size: {caption}px; }}
QLabel[role="stop"] {{ color: {c['stop']}; }}
QLabel[role="headline"] {{ font-size: 13px; font-weight: 700; }}
QLabel[role="title"] {{ font-size: 24px; font-weight: 600; }}
QLabel[role="value"] {{ font-size: 23px; font-weight: 600; color: {c['accent']}; }}
QLabel[role="section"] {{ font-weight: 600; }}
QLabel[role="subhead"] {{ font-size: 11px; font-weight: 600; }}

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
  border: 1px solid rgba(255,255,255,0.10); padding: 5px 11px; font-size: 12px; }}
QPushButton[kind="header"]:hover {{ border-color: rgba(255,255,255,0.22); }}
QPushButton[kind="header"]:pressed {{ background: rgba(35,42,49,0.6); }}
QPushButton[kind="segment"] {{ background: transparent; border: none; border-radius: 6px; padding: 3px 10px; font-weight: 400; }}
QPushButton[kind="segment"]:checked {{ background: {c['control']}; color: white; }}
#Segments {{ background: {c['well']}; border: 1px solid {c['border']}; border-radius: 7px; }}
#SegmentSeparator {{ background: {c['border']}; }}
QPushButton[kind="stepper"] {{ padding: 0; border-radius: 3px; background: {c['surface']}; }}
QPushButton[kind="menu"] {{ padding: 4px 22px 4px 11px; }}
QPushButton[kind="menu"]::menu-indicator {{ image: url({chevron_menu}); subcontrol-position: right center; subcontrol-origin: padding; right: 7px; width: 9px; height: 9px; }}
QPushButton[kind="disclosure"] {{ background: transparent; border: none; text-align: left; padding: 3px 0; font-weight: 400; }}

QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {field}; border: 1px solid {c['border']};
  border-radius: 5px; padding: 2px 6px; min-height: 18px; selection-background-color: {c['control']}; }}
QPlainTextEdit, QTextEdit {{ background: {c['well']}; border: 1px solid {c['border']};
  border-radius: 6px; padding: 4px 6px; selection-background-color: {c['control']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit[invalid="true"] {{ border-color: {c['stop']}; }}
QComboBox {{ background: {picker}; border: none; border-radius: 6px; padding: 3px 26px 3px 9px; color: {c['accent']}; font-weight: 500; min-height: 18px; }}
QComboBox:hover {{ background: {picker_hover}; }}
QComboBox:disabled {{ color: {c['secondary']}; background: rgba(128,128,128,0.08); }}
QComboBox::drop-down {{ border: none; width: 22px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url({updown}); width: 10px; height: 14px; }}
QComboBox::down-arrow:disabled {{ image: url({updown_plain}); }}
QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
  selection-background-color: {c['control']}; selection-color: white; padding: 4px; outline: none; }}
#Header QComboBox {{ background: {c['header_control']}; color: {c['header_text']}; border: none; font-size: 12px; font-weight: 400; }}
#Header QLabel#HeaderLabel {{ font-size: 13px; }}
#Header QComboBox:hover {{ background: #2C343C; }}
#Header QComboBox::down-arrow {{ image: url({updown_header}); }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 4px; border: 1px solid {c['border']}; background: {c['well']}; }}
QCheckBox::indicator:checked {{ background: {c['lime']}; border-color: {c['lime']}; image: url({check}); }}
QCheckBox::indicator:disabled {{ background: rgba(128,128,128,0.15); }}
QCheckBox[role="caption"] {{ font-size: {caption}px; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['surface']}; border: 1px solid {c['secondary']}; width: 16px; height: 16px;
  margin: -7px 0; border-radius: 8px; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px 1px; }}
QScrollBar::handle:vertical {{ background: {handle}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['secondary']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 1px 2px; }}
QScrollBar::handle:horizontal {{ background: {handle}; border-radius: 3px; min-width: 30px; }}
#ProgramRow {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
#ProgramRow[state="structure"] {{ background: {c['well']}; }}
#ProgramRow[state="selected"] {{ border: 2px solid {c['accent']}; }}
#ProgramRow[state="active"] {{ background: rgba(163,234,47,0.16); border: 2px solid {c['accent']}; }}
#ProgramRow[state="problem"] {{ border: 2px solid {c['stop']}; }}
#Banner {{ background: rgba(255,176,32,0.10); border: 1px solid rgba(255,176,32,0.35); border-radius: 8px; }}
#Banner QLabel {{ color: {c['warning']}; }}
QDialog {{ background: {c['surface']}; }}
QMessageBox {{ background: {c['surface']}; }}
QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; padding: 4px; }}
QMenu::item {{ padding: 4px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {c['control']}; color: white; }}
QTabBar::tab {{ padding: 6px 14px; }}
"""
