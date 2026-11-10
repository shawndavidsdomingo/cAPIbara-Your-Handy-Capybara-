import random
import string

import stats

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QApplication,
                               QScrollArea, QSizePolicy)


class ElidedLabel(QLabel):
    """A label that cuts long text with '...' to fit its current width."""

    def __init__(self, text):
        super().__init__()
        self.full_text = text
        self.setToolTip(text)                       # hover shows the full text
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Ignore the text's own width, so the grid decides the size
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.show_elided()

    def show_elided(self):
        self.setText(self.fontMetrics().elidedText(
            self.full_text, Qt.ElideRight, self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_elided()


class UrlPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        heading = QLabel("URL Shortening")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        # Input + Shorten button (Enter key works too)
        self.long_url = QLineEdit()
        self.long_url.setPlaceholderText("Paste your long URL here")
        self.long_url.returnPressed.connect(self.shorten)
        shorten = QPushButton("Shorten")
        shorten.clicked.connect(self.shorten)
        layout.addWidget(self.long_url)
        layout.addWidget(shorten)

        # Output + Copy button
        self.short_url = QLineEdit()
        self.short_url.setReadOnly(True)
        self.short_url.setPlaceholderText("Short URL appears here")
        copy = QPushButton("Copy")
        copy.setMinimumWidth(85)
        copy.clicked.connect(lambda: self.copy_url(self.short_url.text()))
        row = QHBoxLayout()
        row.addWidget(self.short_url, 1)
        row.addWidget(copy)
        layout.addLayout(row)

        layout.addWidget(QLabel("History"))
        layout.addWidget(self.build_history(), 1)

    def build_history(self):
        """Scrollable grid: one row per shortened link."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        holder = QWidget()
        self.grid = QGridLayout(holder)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setHorizontalSpacing(15)
        self.grid.setVerticalSpacing(10)
        self.grid.setAlignment(Qt.AlignTop)         # rows stay at the top

        for col, text in enumerate(("Shortened URL", "Original URL", "Action")):
            header = QLabel(text)
            header.setObjectName("bold")
            self.grid.addWidget(header, 0, col, Qt.AlignTop)

        self.grid.setColumnStretch(0, 2)            # short : original = 2 : 4
        self.grid.setColumnStretch(1, 4)
        self.grid.setColumnMinimumWidth(2, 85)      # room for the Copy button
        self.history_count = 0

        scroll.setWidget(holder)
        return scroll

    def shorten(self):
        url = self.long_url.text().strip()
        if not url:
            return
        code = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        short = f"https://short.ly/{code}"          # dummy link (real logic later)
        self.short_url.setText(short)
        self.add_history(short, url)
        stats.record_link()

    def add_history(self, short, original):
        row = self.history_count + 1                # row 0 is the header

        copy = QPushButton("Copy")
        copy.setFixedSize(85, 32)
        copy.setCursor(Qt.PointingHandCursor)
        copy.clicked.connect(lambda checked=False, link=short: self.copy_url(link))

        self.grid.addWidget(ElidedLabel(short), row, 0, Qt.AlignTop)
        self.grid.addWidget(ElidedLabel(original), row, 1, Qt.AlignTop)
        self.grid.addWidget(copy, row, 2, Qt.AlignTop | Qt.AlignHCenter)
        self.grid.setRowMinimumHeight(row, 32)
        self.history_count += 1

    def copy_url(self, url):
        if url:
            QApplication.clipboard().setText(url)