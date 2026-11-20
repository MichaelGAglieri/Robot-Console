# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Small building blocks: cards, captions, buttons, disclosure groups, segmented controls."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget)
from .i18n import T
from . import theme


def label(text='', role=None, wrap=True, selectable=False):
    widget = QLabel(T(text) if text else '')
    if role:
        widget.setProperty('role', role)
    widget.setWordWrap(wrap)
    if selectable:
        widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def caption(text='', small=False):
    return label(text, 'small' if small else 'caption')


def set_role(widget, role):
    if widget.property('role') != role:
        widget.setProperty('role', role)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def button(text, kind=None, slot=None, tip=None):
    widget = QPushButton(T(text))
    if kind:
        widget.setProperty('kind', kind)
    if slot:
        widget.clicked.connect(slot)
    if tip:
        widget.setToolTip(T(tip))
    widget.setCursor(Qt.PointingHandCursor)
    return widget


def checkbox(text, slot=None):
    widget = QCheckBox(T(text))
    if slot:
        widget.toggled.connect(slot)
    return widget


def combo(items, slot=None):
    """items: list of (value, text). slot receives the value."""
    widget = QComboBox()
    for value, text in items:
        widget.addItem(T(text), value)
    if slot:
        widget.activated.connect(lambda _i: slot(widget.currentData()))
    return widget


def set_combo_items(widget, items, current=None):
    """Replace items only when they changed, keeping the selection."""
    values = [(value, T(text)) for value, text in items]
    existing = [(widget.itemData(i), widget.itemText(i)) for i in range(widget.count())]
    if values != existing:
        widget.blockSignals(True)
        widget.clear()
        for value, text in values:
            widget.addItem(text, value)
        widget.blockSignals(False)
    select_combo(widget, current)


def select_combo(widget, value):
    index = widget.findData(value)
    if index >= 0 and index != widget.currentIndex():
        widget.blockSignals(True)
        widget.setCurrentIndex(index)
        widget.blockSignals(False)


def line(placeholder='', width=None, text=''):
    widget = QLineEdit(text)
    widget.setPlaceholderText(T(placeholder))
    if width:
        widget.setFixedWidth(width)
    return widget


def set_text_if_idle(edit, text):
    """Refresh a field from the controller unless the operator is typing in it."""
    if not edit.hasFocus() and edit.text() != text:
        edit.setText(text)


def row(*items, spacing=10, stretch_at=None):
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(0, 0, 0, 0)
    for index, item in enumerate(items):
        if stretch_at == index:
            layout.addStretch(1)
        if item is None:
            layout.addStretch(1)
        elif isinstance(item, QLabel) and item.wordWrap() and len(item.text()) <= 60:
            # Short labels beside other controls keep one line instead of collapsing.
            item.setWordWrap(False)
            layout.addWidget(item)
        elif isinstance(item, QLayout):
            layout.addLayout(item)
        else:
            layout.addWidget(item)
    return layout


def column(*items, spacing=8):
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(0, 0, 0, 0)
    for item in items:
        if isinstance(item, QLayout):
            layout.addLayout(item)
        elif item is not None:
            layout.addWidget(item)
    return layout


def well(layout=None, name='Well', margins=12):
    frame = QFrame()
    frame.setObjectName(name)
    inner = layout or QVBoxLayout()
    inner.setContentsMargins(margins, margins, margins, margins)
    frame.setLayout(inner)
    return frame


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


class Card(QFrame):
    """Panel with an uppercase technical title, like the macOS app."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName('Card')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(18, 14, 18, 12)
        bar = QFrame()
        bar.setObjectName('CardBar')
        bar.setFixedSize(3, 14)
        self.title = QLabel(T(title).upper())
        self.title.setObjectName('CardTitle')
        head.addWidget(bar)
        head.addSpacing(8)
        head.addWidget(self.title)
        head.addStretch(1)
        self.head = head
        outer.addLayout(head)
        rule = QFrame()
        rule.setObjectName('CardRule')
        rule.setFixedHeight(1)
        outer.addWidget(rule)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(18, 14, 18, 18)
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def add(self, *items):
        for item in items:
            if isinstance(item, QLayout):
                self.body.addLayout(item)
            elif item is not None:
                self.body.addWidget(item)
        return self


class Disclosure(QWidget):
    """Collapsible group (DisclosureGroup)."""
    toggled = Signal(bool)

    def __init__(self, title, expanded=False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.header = QPushButton()
        self.header.setProperty('kind', 'disclosure')
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(lambda: self.set_expanded(not self.expanded))
        self.title = T(title)
        layout.addWidget(self.header)
        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(14, 4, 0, 4)
        self.body.setSpacing(10)
        layout.addWidget(self.content)
        self.expanded = None
        self.set_expanded(expanded)

    def set_expanded(self, value):
        if value == self.expanded:
            return
        self.expanded = value
        self.header.setText(('▾  ' if value else '▸  ') + self.title)
        self.content.setVisible(value)
        self.toggled.emit(value)

    def add(self, *items):
        for item in items:
            if isinstance(item, QLayout):
                self.body.addLayout(item)
            elif item is not None:
                self.body.addWidget(item)
        return self


class Segmented(QFrame):
    """Mutually exclusive buttons; emits the selected value."""
    changed = Signal(object)

    def __init__(self, items, current=None, parent=None):
        super().__init__(parent)
        self.setObjectName('Segments')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for value, text in items:
            b = QPushButton(T(text))
            b.setProperty('kind', 'segment')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, v=value: self._clicked(v))
            self.group.addButton(b)
            self.buttons[value] = b
            layout.addWidget(b)
        self.value = None
        self.set_value(current if current is not None else items[0][0])

    def _clicked(self, value):
        if value != self.value:
            self.set_value(value)
            self.changed.emit(value)

    def set_value(self, value):
        self.value = value
        if value in self.buttons:
            self.buttons[value].setChecked(True)


class StatusChip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ''
        self.color = QColor('#9AA5B0')
        self.filled = False
        self.setMinimumHeight(26)

    def set(self, text, color, filled=False):
        text = T(text)
        if (text, QColor(color).name(), filled) != (self.text, self.color.name(), self.filled):
            self.text, self.color, self.filled = text, QColor(color), filled
            self.updateGeometry()
            self.update()

    def sizeHint(self):
        width = self.fontMetrics().horizontalAdvance(self.text) + 40
        return QSize(width, 26)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        if self.filled:
            p.setBrush(self.color)
            p.setPen(Qt.NoPen)
        else:
            fill = QColor(self.color)
            fill.setAlphaF(.12)
            edge = QColor(self.color)
            edge.setAlphaF(.45)
            p.setBrush(fill)
            p.setPen(QPen(edge, 1))
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        dot = theme.color('ink') if self.filled else self.color
        p.setBrush(dot)
        p.setPen(Qt.NoPen)
        p.drawEllipse(12, rect.center().y() - 3, 7, 7)
        font = p.font()
        font.setBold(True)
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(theme.color('ink') if self.filled else theme.color('header_text'))
        p.drawText(rect.adjusted(25, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text)


def confirm(parent, title, text, accept='Conferma', destructive=False, cancel='Annulla'):
    """Modal confirmation; True only on the explicit accept button."""
    box = QMessageBox(parent)
    box.setWindowTitle(T(title))
    box.setText('<b>' + T(title) + '</b>')
    box.setInformativeText(T(text))
    yes = box.addButton(T(accept), QMessageBox.DestructiveRole if destructive else QMessageBox.AcceptRole)
    no = box.addButton(T(cancel), QMessageBox.RejectRole)
    box.setDefaultButton(no if destructive else yes)
    box.exec()
    return box.clickedButton() is yes


def choose(parent, title, text, options, cancel='Annulla'):
    """Several explicit choices; returns the chosen key or None."""
    box = QMessageBox(parent)
    box.setWindowTitle(T(title))
    box.setText('<b>' + T(title) + '</b>')
    box.setInformativeText(T(text))
    buttons = {}
    for key, caption_text, destructive in options:
        buttons[box.addButton(T(caption_text), QMessageBox.DestructiveRole if destructive else QMessageBox.AcceptRole)] = key
    box.addButton(T(cancel), QMessageBox.RejectRole)
    box.exec()
    return buttons.get(box.clickedButton())


def grid(columns=2, spacing=10):
    layout = QGridLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def expanding(widget):
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return widget
