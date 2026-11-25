"""Tiny helpers so every screen builds labels, inputs and buttons the same way.

Colors and fonts are NOT set here. They come from theme.py through the
objectName ("title", "heading", "bold", "muted", "error", "secondary", ...).
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

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