# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Small building blocks: cards, captions, buttons, disclosure groups, segmented controls."""
from PySide6.QtCore import QEvent, QRectF, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)
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


def tinted(widget, name, tint, size=14):
    """Give a label or button a line icon that follows light/dark changes (see retint)."""
    widget.tint = (name, tint, size)
    if isinstance(widget, QLabel):
        widget.setPixmap(theme.icon(name, tint, size).pixmap(size, size))
    else:
        widget.setIcon(theme.icon(name, tint, size))
        widget.setIconSize(QSize(size, size))
    return widget


def retint(root):
    """Re-render tinted icons after the appearance changed."""
    for widget in [root] + root.findChildren(QWidget):
        if getattr(widget, 'tint', None):
            tinted(widget, *widget.tint)
        elif isinstance(widget, Disclosure):
            widget.paint_chevron()


def icon_label(name, tint='accent', size=14):
    widget = QLabel()
    widget.setFixedSize(size + 2, size + 2)
    widget.setAlignment(Qt.AlignCenter)
    return tinted(widget, name, tint, size)


def button(text, kind=None, slot=None, tip=None, icon=None, tint=None):
    widget = QPushButton((' ' if icon else '') + T(text))  # a little air between icon and text
    if icon:
        tinted(widget, icon, tint or ('header_text' if kind == 'header' else 'white' if kind == 'danger' else 'text'), 14)
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


class ToggleSwitch(QCheckBox):
    """macOS-style switch, used where the macOS app shows one (.toggleStyle(.switch))."""
    TRACK = QSize(30, 18)

    def sizeHint(self):
        text = self.text()
        width = self.TRACK.width() + (8 + self.fontMetrics().horizontalAdvance(text) if text else 0)
        return QSize(width + 2, max(self.TRACK.height() + 2, self.fontMetrics().height() + 4))

    minimumSizeHint = sizeHint

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, (self.height() - self.TRACK.height()) / 2, self.TRACK.width(), self.TRACK.height())
        on = self.isChecked()
        fill = theme.color('accent' if not theme.is_dark() else 'lime') if on else QColor(theme.color('border'))
        if not self.isEnabled():
            fill.setAlphaF(.45)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        knob = track.height() - 4
        x = track.right() - knob - 2 if on else track.left() + 2
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, track.top() + 2.6, knob, knob))
        p.setBrush(QColor('#FFFFFF'))
        p.drawEllipse(QRectF(x, track.top() + 2, knob, knob))
        if self.text():
            p.setPen(theme.color('text' if self.isEnabled() else 'secondary'))
            p.drawText(QRectF(track.right() + 8, 0, self.width() - track.right() - 8, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


def switch(text='', slot=None):
    widget = ToggleSwitch(T(text) if text else '')
    widget.setCursor(Qt.PointingHandCursor)
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


def hline():
    """Thin divider (SwiftUI Divider)."""
    rule = QFrame()
    rule.setObjectName('CardRule')
    rule.setFixedHeight(1)
    return rule


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


class _FitScroll(QScrollArea):
    """Shows the whole content, or at most `limit` points with a scroll bar (resized panels)."""

    def __init__(self, content):
        super().__init__()
        self.setObjectName('CardBody')
        self.limit = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setWidget(content)
        content.installEventFilter(self)

    def natural(self):
        content = self.widget()
        width = self.viewport().width() or content.width()
        if content.hasHeightForWidth() and width > 0:
            return content.heightForWidth(width)
        return content.sizeHint().height()

    def sizeHint(self):
        height = self.natural()
        if self.limit:
            height = min(self.limit, height)
        return QSize(super().sizeHint().width(), max(1, height))

    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.LayoutRequest:
            self.updateGeometry()
        return False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.updateGeometry()


class _Grip(QWidget):
    """Capsule at the bottom of a panel: drag to change only its height, double click to fit."""

    def __init__(self, card):
        super().__init__()
        self.card = card
        self.hover = False
        self.start = None
        self.setFixedHeight(16)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip(T('Trascina per cambiare solo l’altezza. Doppio clic per adattare al contenuto.'))

    def enterEvent(self, _e):
        self.hover = True
        self.update()

    def leaveEvent(self, _e):
        self.hover = False
        self.update()

    def mousePressEvent(self, e):
        self.start = (e.globalPosition().y(), self.card.scroll.height())

    def mouseMoveEvent(self, e):
        if self.start:
            y, height = self.start
            self.card.set_limit(height + e.globalPosition().y() - y)

    def mouseReleaseEvent(self, _e):
        self.start = None

    def mouseDoubleClickEvent(self, _e):
        self.card.set_limit(None)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = theme.color('accent') if self.hover else theme.color('border')
        if self.hover:
            color.setAlphaF(.7)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(self.width() / 2 - 18, self.height() / 2 - 2, 36, 4), 2, 2)


class Card(QFrame):
    """Panel with an uppercase technical title, like the macOS app.

    Resizable panels end with a grip that limits only their height (saved per panel);
    the content then scrolls inside the card. "Adatta" restores the natural height.
    """

    def __init__(self, title, parent=None, resizable=True):
        super().__init__(parent)
        self.setObjectName('Card')
        self.key = 'panelHeight/' + title
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0 if resizable else 18)
        outer.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(20, 15, 20, 10)
        head.setSpacing(0)
        bar = QFrame()
        bar.setObjectName('CardBar')
        bar.setFixedSize(3, 14)
        self.title = QLabel(T(title).upper())
        self.title.setObjectName('CardTitle')
        head.addWidget(bar)
        head.addSpacing(9)
        head.addWidget(self.title)
        head.addStretch(1)
        self.fit = QPushButton(T('Adatta'))
        self.fit.setObjectName('CardFit')
        self.fit.setCursor(Qt.PointingHandCursor)
        self.fit.setToolTip(T('Ripristina l’altezza naturale del contenuto'))
        self.fit.clicked.connect(lambda: self.set_limit(None))
        self.fit.hide()
        head.addWidget(self.fit)
        self.head = head
        outer.addLayout(head)
        rule = QFrame()
        rule.setObjectName('CardRule')
        rule.setFixedHeight(1)
        outer.addWidget(rule)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(20, 14, 20, 2)
        self.body.setSpacing(14)
        self.scroll = _FitScroll(content)
        outer.addWidget(self.scroll)
        self.resizable = resizable
        if resizable:
            outer.addSpacing(4)
            outer.addWidget(_Grip(self))
            outer.addSpacing(4)
            stored = QSettings().value(self.key, 0, float) if QSettings().contains(self.key) else 0
            if stored:
                self.set_limit(stored, save=False)

    def set_limit(self, height, save=True):
        height = None if not height else min(1600, max(28, int(height)))
        self.scroll.limit = height
        self.fit.setVisible(height is not None)
        self.scroll.updateGeometry()
        if save:
            settings = QSettings()
            if height:
                settings.setValue(self.key, height)
            else:
                settings.remove(self.key)

    def add(self, *items):
        for item in items:
            if isinstance(item, QLayout):
                self.body.addLayout(item)
            elif isinstance(item, Segmented):
                self.body.addWidget(item, 0, Qt.AlignLeft)
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
        self.header.setText('  ' + self.title)
        self.paint_chevron()
        self.content.setVisible(value)
        self.toggled.emit(value)

    def paint_chevron(self):
        self.header.setIcon(theme.icon('chevron-down' if self.expanded else 'chevron-right', 'text', 12))
        self.header.setIconSize(QSize(11, 11))

    def add(self, *items):
        for item in items:
            if isinstance(item, QLayout):
                self.body.addLayout(item)
            elif isinstance(item, Segmented):
                self.body.addWidget(item, 0, Qt.AlignLeft)
            elif item is not None:
                self.body.addWidget(item)
        return self


class Segmented(QFrame):
    """Mutually exclusive buttons (segmented picker); emits the selected value.

    segment_width gives every segment the same width, like the macOS segmented control.
    """
    changed = Signal(object)

    def __init__(self, items, current=None, parent=None, segment_width=None):
        super().__init__(parent)
        self.setObjectName('Segments')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.buttons = {}
        self.separators = []
        for index, (value, text) in enumerate(items):
            if index:
                sep = QFrame()
                sep.setObjectName('SegmentSeparator')
                sep.setFixedSize(1, 14)
                layout.addWidget(sep, 0, Qt.AlignVCenter)
                self.separators.append(sep)
            b = QPushButton(T(text))
            b.setProperty('kind', 'segment')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            if segment_width:
                b.setMinimumWidth(segment_width)
            b.clicked.connect(lambda _c=False, v=value: self._clicked(v))
            self.group.addButton(b)
            self.buttons[value] = b
            layout.addWidget(b)
        self.order = [v for v, _ in items]
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)  # never stretched, like macOS
        self.value = None
        self.set_value(current if current is not None else items[0][0])
        self.setMaximumWidth(self.sizeHint().width())

    def _clicked(self, value):
        if value != self.value:
            self.set_value(value)
            self.changed.emit(value)

    def set_value(self, value):
        self.value = value
        if value in self.buttons:
            self.buttons[value].setChecked(True)
        selected = self.order.index(value) if value in self.order else -1
        for index, sep in enumerate(self.separators):  # separator between segment index and index+1
            sep.setVisible(selected not in (index, index + 1))


class Stepper(QWidget):
    """macOS Stepper: two small arrows that change an integer value by one."""
    valueChanged = Signal(int)

    def __init__(self, minimum, maximum, value=None, parent=None):
        super().__init__(parent)
        self.minimum, self.maximum = minimum, maximum
        self._value = minimum if value is None else value
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.buttons = []
        for name, delta in (('chevron-up', 1), ('chevron-down', -1)):
            b = QPushButton()
            b.setProperty('kind', 'stepper')
            b.setFixedSize(18, 12)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoRepeat(True)
            tinted(b, name, 'text', 9)
            b.clicked.connect(lambda _c=False, d=delta: self.setValue(self._value + d, emit=True))
            layout.addWidget(b)
            self.buttons.append(b)

    def value(self):
        return self._value

    def setValue(self, value, emit=False):
        value = max(self.minimum, min(self.maximum, int(value)))
        if value != self._value:
            self._value = value
            if emit and not self.signalsBlocked():
                self.valueChanged.emit(value)


def preset_menu_button(text, items, slot):
    """Menu button (SwiftUI Menu): a plain button that opens a list of choices."""
    from PySide6.QtWidgets import QMenu
    widget = button(text)
    widget.setProperty('kind', 'menu')
    menu = QMenu(widget)
    for value, caption_text in items:
        action = menu.addAction(T(caption_text))
        action.triggered.connect(lambda _c=False, v=value: slot(v))
    widget.setMenu(menu)
    widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return widget


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
