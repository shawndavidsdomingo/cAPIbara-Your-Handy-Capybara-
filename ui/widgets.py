"""Tiny helpers so every screen builds labels, inputs and buttons the same way.

Colors and fonts are NOT set here. They come from theme.py through the
objectName ("title", "heading", "bold", "muted", "error", "secondary", ...).
"""
import os

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea,
                               QWidget)

from core import zoom
from core.paths import resource_path
from core.zoom import px

ASSETS = resource_path("assets")
LOGO_PATH = os.path.join(ASSETS, "logo.png")     # the capybara, transparent background
ICON_PATH = os.path.join(ASSETS, "icon.png")     # square version for window icons


def make_label(text="", style=None, center=False):
    """style = a label name from theme.py, e.g. 'title', 'heading', 'muted'."""
    label = QLabel(text)
    if style:
        label.setObjectName(style)
    if center:
        label.setAlignment(Qt.AlignCenter)
    return label


def make_logo(height):
    """The cAPIbara logo scaled to `height` pixels. Empty if the file is missing."""
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(LOGO_PATH)
    if not pixmap.isNull():
        label.setPixmap(pixmap.scaledToHeight(
            px(height), Qt.TransformationMode.SmoothTransformation))
    return label


def make_card():
    """An empty card: a white-ish panel with a thin border, painted by theme.py."""
    card = QWidget()
    card.setObjectName("card")
    card.setAttribute(Qt.WA_StyledBackground, True)   # lets the stylesheet paint it
    return card


def make_error_label():
    """Red message line that is empty until something goes wrong.
    It wraps, so a long message is never cut off in a fixed-size window."""
    label = make_label("", "error", center=True)
    label.setWordWrap(True)
    return label


def make_input(placeholder, password=False):
    box = QLineEdit()
    box.setPlaceholderText(placeholder)
    if password:
        box.setEchoMode(QLineEdit.Password)
    return box


def make_button(text, on_click, secondary=False):
    """secondary=True gives the flat outline style from theme.py."""
    button = QPushButton(text)
    if secondary:
        button.setObjectName("secondary")
    button.clicked.connect(on_click)
    return button


def fit_window(window, width, height):
    """Give a fixed-size window its size at the current zoom, but never taller
    or wider than the screen (the rest scrolls, see make_scroller)."""
    screen = QApplication.primaryScreen().availableGeometry()
    window.setFixedSize(min(px(width), screen.width() - 20),
                        min(px(height), screen.height() - 60))


def make_scroller(widget):
    """Wrap a widget in a scroll area that shows no frame and no sideways bar."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


# ---------- Zoom (see core/zoom.py) ----------

def _change_zoom(level):
    if level is not None:
        from ui import navigation          # imported here: navigation imports the windows
        navigation.set_zoom(level)


def zoom_in():
    _change_zoom(zoom.step(1))


def zoom_out():
    _change_zoom(zoom.step(-1))


def zoom_reset():
    _change_zoom(zoom.DEFAULT)


class WheelZoom(QObject):
    """Ctrl + mouse wheel zooms the whole app, like a web browser: wheel up =
    bigger, wheel down = smaller.

    It watches every wheel event in the app, so it works over any widget (a table
    or a text box would otherwise keep the wheel for itself). The turns are added
    up and applied once the wheel stops, because each zoom redraws the window."""

    PAUSE_MS = 200        # short, so zooming feels responsive (each step still applies once)

    def __init__(self, app):
        super().__init__(app)
        self.notches = 0.0                       # wheel turns not applied yet
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.PAUSE_MS)
        self.timer.timeout.connect(self.apply)

    def eventFilter(self, _watched, event):
        if event.type() != QEvent.Wheel or not event.modifiers() & Qt.ControlModifier:
            return False                         # a normal scroll: leave it alone
        from ui import navigation
        # not while a pop-up is open: the window behind it must not be redrawn
        if QApplication.activeWindow() is navigation._current:
            self.notches += event.angleDelta().y() / 120     # one click of a wheel = 120
            self.timer.start()
        return True                              # Ctrl + wheel never scrolls anything

    def apply(self):
        steps, self.notches = int(self.notches), 0.0
        if steps:
            _change_zoom(zoom.shifted(steps))


_wheel_zoom = None


def enable_zoom(window):
    """Turn zoom on for a window: Ctrl + mouse wheel (app-wide, set up once), and
    the keys Ctrl and +  /  Ctrl and -  /  Ctrl and 0 like a web browser."""
    global _wheel_zoom
    if _wheel_zoom is None:
        app = QApplication.instance()
        _wheel_zoom = WheelZoom(app)
        app.installEventFilter(_wheel_zoom)
    for keys, action in ((("Ctrl++", "Ctrl+="), zoom_in), (("Ctrl+-",), zoom_out),
                         (("Ctrl+0",), zoom_reset)):
        for key in keys:
            QShortcut(QKeySequence(key), window, activated=action)


class SegmentedControl(QWidget):
    """A row of joined buttons where exactly one is selected (like a radio group).

    Use it instead of a dropdown for a few choices: every option is visible and
    one click picks it. It answers like a combo box: currentText() and
    setCurrentText(), plus a `changed` signal that carries the new text."""

    changed = Signal(str)

    def __init__(self, options, current=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        last = len(options) - 1
        for i, text in enumerate(options):
            button = QPushButton(text)
            button.setObjectName("segment")           # styled in theme.py
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            position = "only" if last == 0 else "first" if i == 0 else "last" if i == last else "middle"
            button.setProperty("edge", position)      # theme.py rounds the outer ends
            self.group.addButton(button)
            layout.addWidget(button)
            self.buttons[text] = button
        self.group.buttonClicked.connect(lambda button: self.changed.emit(button.text()))
        self.setCurrentText(current if current in self.buttons else options[0])

    def currentText(self):
        return self.group.checkedButton().text()

    def setCurrentText(self, text):
        if text in self.buttons:
            self.buttons[text].setChecked(True)