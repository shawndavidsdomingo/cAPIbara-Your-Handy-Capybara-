from datetime import datetime, timezone

from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QApplication,
                               QScrollArea, QSizePolicy, QMessageBox)

import session
import url_service
from url_service import ShortenError
from widgets import make_label, make_error_label


class ElidedLabel(QLabel):
    """A label that cuts long text with '...' to fit its current width.
    Click it to copy the full text: `clicked` sends that text."""
    clicked = Signal(str)

    def __init__(self, text):
        super().__init__()
        self.full_text = text
        self.setToolTip(f"{text}\nClick to copy")   # hover shows the full text
        self.setCursor(Qt.PointingHandCursor)
        # Ignore the text's own width, so the grid decides the size
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.show_elided()

    def show_elided(self):
        self.setText(self.fontMetrics().elidedText(
            self.full_text, Qt.ElideRight, self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_elided()

    def set_underline(self, on):
        font = self.font()
        font.setUnderline(on)
        self.setFont(font)
        self.show_elided()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.set_underline(True)                    # hover: looks clickable

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.set_underline(False)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if (event.button() == Qt.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit(self.full_text)


class SortHeader(QLabel):
    """A column title you can click to sort by that column."""
    clicked = Signal(int)

    def __init__(self, text, column, tip):
        super().__init__(text)
        self.column = column
        self.setObjectName("bold")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if (event.button() == Qt.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit(self.column)


class ShortenWorker(QObject):
    """Runs the network call on a background thread so the window never freezes."""
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.done.emit(url_service.ulvis_shorten(self.url))
        except ShortenError as error:
            self.failed.emit(str(error))
        except Exception:                           # never leave the button stuck
            self.failed.emit("Something went wrong. Please try again.")


def local_time(stamp):
    """SQLite stores UTC. Show it in the computer's own time zone."""
    try:
        utc = datetime.strptime(stamp[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return utc.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return stamp or ""


class UrlPage(QWidget):
    HEADERS = ("Short URL", "Original URL", "Shortened", "Clicks", "Actions")
    SORT_COLUMNS = {0: "short", 1: "original", 2: "date"}   # column -> sort name
    SORT_TIPS = {0: "Click to sort: default, A to Z, Z to A",
                 1: "Click to sort: default, A to Z, Z to A",
                 2: "Click to sort: default, earliest, latest"}

    def __init__(self):
        super().__init__()
        self.thread = None          # keep references while a request runs,
        self.worker = None          # or Python may delete them mid-flight
        self.pending = None         # the long URL of the request in progress
        self.links = []             # every saved link (search and sort work on this)
        self.sort_col = -1          # column being sorted (-1 = none)
        self.sort_state = 0         # 0 = default, 1 = A to Z / earliest, 2 = Z to A / latest

        layout = QVBoxLayout(self)
        layout.addWidget(make_label("URL Shortening", "heading"))

        # Input row: long URL + Shorten button (Enter key works too)
        self.long_url = QLineEdit()
        self.long_url.setPlaceholderText("Paste your long URL here (http:// or https://)")
        self.long_url.returnPressed.connect(self.shorten)
        self.shorten_button = QPushButton("Shorten")
        self.shorten_button.setMinimumWidth(110)
        self.shorten_button.clicked.connect(self.shorten)
        input_row = QHBoxLayout()
        input_row.addWidget(self.long_url, 1)
        input_row.addWidget(self.shorten_button)
        layout.addLayout(input_row)

        # Output + Copy button
        self.short_url = QLineEdit()
        self.short_url.setReadOnly(True)
        self.short_url.setPlaceholderText("Short URL appears here")
        copy = QPushButton("Copy")
        copy.setMinimumWidth(85)
        copy.clicked.connect(lambda: self.copy_url(self.short_url.text()))
        out_row = QHBoxLayout()
        out_row.addWidget(self.short_url, 1)
        out_row.addWidget(copy)
        layout.addLayout(out_row)

        self.error = make_error_label()
        self.note = make_label("", "success", center=True)
        layout.addWidget(self.error)
        layout.addWidget(self.note)

        history_row = QHBoxLayout()
        history_row.addWidget(QLabel("History"))
        history_row.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search short or original link")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(self.render_history)
        history_row.addWidget(self.search)
        layout.addLayout(history_row)
        layout.addWidget(self.build_history(), 1)

    # ---------- Page contract ----------

    def refresh(self):
        """Called by MainWindow every time this page opens."""
        self.reload_history()

    def shutdown(self):
        """Called by MainWindow on close: let a running request finish first."""
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(url_service.TIMEOUT * 1000 + 2000)

    # ---------- History ----------

    def build_history(self):
        """Scrollable grid: one row per saved link."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        holder = QWidget()
        self.grid = QGridLayout(holder)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setHorizontalSpacing(15)
        self.grid.setVerticalSpacing(10)
        self.grid.setAlignment(Qt.AlignTop)         # rows stay at the top
        self.grid.setColumnStretch(0, 2)            # short : original = 2 : 3
        self.grid.setColumnStretch(1, 3)
        self.grid.setColumnMinimumWidth(0, 140)     # short link stays readable
        self.grid.setColumnMinimumWidth(2, 105)     # created
        self.grid.setColumnMinimumWidth(3, 50)      # clicks
        self.grid.setColumnMinimumWidth(4, 175)     # Open / Copy / trash
        self.row_count = 0

        scroll.setWidget(holder)
        return scroll

    def clear_grid(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.hide()                       # gone from the screen right away
                widget.setParent(None)
                widget.deleteLater()
        for row in range(self.row_count + 2):
            self.grid.setRowMinimumHeight(row, 0)

    def reload_history(self):
        """Read the links from the database, then draw them (search and sort stay)."""
        self.links = url_service.get_links(session.current()["id"])
        self.render_history()

    def show_newest(self):
        """After a new or reused link: clear search and sort so it shows at the top."""
        self.sort_col, self.sort_state = -1, 0
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)

    def sort_by_column(self, col):
        """Click a header: Default -> A to Z (earliest) -> Z to A (latest) -> Default."""
        if col != self.sort_col:
            self.sort_col = col
            self.sort_state = 1
        else:
            self.sort_state = (self.sort_state + 1) % 3
            if self.sort_state == 0:
                self.sort_col = -1
        self.render_history()

    def render_history(self, _text=None):
        self.clear_grid()
        rows = url_service.arrange_links(
            self.links, self.search.text(),
            self.SORT_COLUMNS.get(self.sort_col), self.sort_state)
        self.row_count = len(rows)

        if not self.links:
            message = "No links yet. Shorten your first one above."
        elif not rows:
            message = "No links match your search."
        else:
            message = None
        if message:
            self.grid.addWidget(make_label(message, "muted"), 0, 0, 1, 5, Qt.AlignTop)
            return

        for col, text in enumerate(self.HEADERS):
            if col in self.SORT_COLUMNS:
                arrow = ""
                if col == self.sort_col:
                    arrow = "  ▲" if self.sort_state == 1 else "  ▼"
                header = SortHeader(text + arrow, col, self.SORT_TIPS[col])
                header.clicked.connect(self.sort_by_column)
            else:
                header = make_label(text, "bold")
            self.grid.addWidget(header, 0, col, Qt.AlignVCenter)
        for row, link in enumerate(rows, start=1):
            self.add_row(row, link)

    def add_row(self, row, link):
        short = ElidedLabel(link["short_url"])
        short.clicked.connect(lambda text: self.copy_url(text, "Short link copied."))
        original = ElidedLabel(link["original_url"])
        original.clicked.connect(lambda text: self.copy_url(text, "Original link copied."))
        self.grid.addWidget(short, row, 0, Qt.AlignVCenter)
        self.grid.addWidget(original, row, 1, Qt.AlignVCenter)
        self.grid.addWidget(QLabel(local_time(link["created_at"])), row, 2, Qt.AlignVCenter)
        self.grid.addWidget(QLabel(str(link["clicks"])), row, 3, Qt.AlignVCenter)

        actions = QWidget()
        box = QHBoxLayout(actions)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        open_btn = QPushButton("Open")
        open_btn.setStyleSheet("padding: 2px 6px;")      # room for the label
        open_btn.setFixedSize(64, 30)
        open_btn.clicked.connect(lambda checked=False, l=link: self.open_link(l))

        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("secondary")
        copy_btn.setStyleSheet("padding: 2px 6px;")
        copy_btn.setFixedSize(64, 30)
        copy_btn.clicked.connect(
            lambda checked=False, l=link: self.copy_url(l["short_url"]))

        trash = QPushButton("🗑")                         # same style as Fake Data
        trash.setObjectName("trash")
        trash.setToolTip("Delete this link")
        trash.setFixedSize(34, 30)
        trash.clicked.connect(lambda checked=False, l=link: self.delete_link(l))

        for button in (open_btn, copy_btn, trash):
            button.setCursor(Qt.PointingHandCursor)
            box.addWidget(button)
        self.grid.addWidget(actions, row, 4, Qt.AlignVCenter)
        self.grid.setRowMinimumHeight(row, 32)

    # ---------- Shorten (validate -> worker thread -> save) ----------

    def show_error(self, text):
        self.error.setText(text)
        self.note.setText("")

    def set_busy(self, busy):
        self.shorten_button.setEnabled(not busy)
        self.shorten_button.setText("Shortening…" if busy else "Shorten")

    def shorten(self):
        if self.thread is not None:                 # one request at a time
            return
        url = self.long_url.text().strip()

        if not url_service.is_valid_url(url):
            self.show_error(url_service.MSG_INVALID_URL)
            return

        user_id = session.current()["id"]
        existing = url_service.find_link(user_id, url)
        if existing:                                # same link again: no new row
            url_service.bump_link(user_id, existing["id"])
            self.short_url.setText(existing["short_url"])
            self.long_url.clear()
            self.show_newest()
            self.reload_history()
            self.show_error("")
            self.note.setText("Already shortened. Moved to the top.")
            return

        self.show_error("")
        self.set_busy(True)
        self.pending = url

        self.thread = QThread(self)
        self.worker = ShortenWorker(url)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup)
        self.thread.start()

    def on_done(self, short):
        url_service.save_link(session.current()["id"], short, self.pending)
        self.short_url.setText(short)
        self.long_url.clear()
        self.show_newest()
        self.reload_history()
        self.note.setText("Link created.")

    def on_failed(self, message):
        self.show_error(message)                    # nothing is saved

    def cleanup(self):
        self.set_busy(False)
        self.worker.deleteLater()
        self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.pending = None

    # ---------- Row actions ----------

    def open_link(self, link):
        QDesktopServices.openUrl(QUrl(link["short_url"]))
        url_service.record_click(session.current()["id"], link["id"])
        self.reload_history()                       # shows the new click count

    def copy_url(self, url, message="Copied to clipboard."):
        if url:
            QApplication.clipboard().setText(url)
            self.error.setText("")
            self.note.setText(message)

    def delete_link(self, link):
        answer = QMessageBox.question(
            self, "Delete link",
            f"Delete {link['short_url']} and its click history?\n"
            "This only removes it from this app, not from Ulvis.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        url_service.delete_link(session.current()["id"], link["id"])
        self.reload_history()
