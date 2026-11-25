"""Tiny helpers so every screen builds labels, inputs and buttons the same way.

Colors and fonts are NOT set here. They come from theme.py through the
objectName ("title", "heading", "bold", "muted", "error", "secondary", ...).
"""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QWidget)

from core.paths import resource_path

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
            height, Qt.TransformationMode.SmoothTransformation))
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