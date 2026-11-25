"""Decides which window is on screen (Login, Register or Main).

Windows never create each other. They just call go_login(), go_register()
or go_main() from here. go_main() needs a logged-in session.

The window classes are imported INSIDE the functions on purpose: the windows
import this module, so importing them at the top would be a circular import.

set_zoom() also lives here: a new zoom needs every window redrawn at the new
size, so it builds a fresh copy of the window on screen. To make that swap
smooth, the new window opens centred where the old one was, and a picture of
the old window fades away over it (_Crossfade).
"""

from PySide6.QtCore import QEvent, QPropertyAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from core import session

_current = None    # the window on screen now
_previous = None   # the window closed one step ago. It is kept alive on purpose:
                   # delete a window while one of its own buttons is still running.
_kind = None       # what the window on screen is: "login", "register" or "main"


def _show(window, kind):
    global _current, _previous, _kind
    window.show()                      # show the new one first, so the app never has 0 windows
    if _current is not None:
        _current.close()
    _previous, _current, _kind = _current, window, kind


def _make(kind, start_page=0):
    if kind == "login":
        from ui.login_window import LoginWindow
        return LoginWindow()
    if kind == "register":
        from ui.register_window import RegisterWindow
        return RegisterWindow()
    from ui.main_window import MainWindow
    return MainWindow(start_page)


def go_login():
    _show(_make("login"), "login")


def go_register():
    _show(_make("register"), "register")


def go_main():
    session.require_login()        # guard: no session, no main window
    _show(_make("main"), "main")


# ---------- Zoom ----------

class _Crossfade(QLabel):
    """A picture of the old window laid over the new one, fading away.

    It sits on top of the new window, lets every click through, follows the
    window if it is resized while settling, and deletes itself when done."""

    DURATION_MS = 180

    def __init__(self, window, snapshot):
        super().__init__(window)
        self.setPixmap(snapshot)
        self.setScaledContents(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(window.rect())
        window.installEventFilter(self)

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self.animation = QPropertyAnimation(effect, b"opacity", self)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setDuration(self.DURATION_MS)
        self.animation.finished.connect(self.deleteLater)

        self.show()
        self.raise_()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.setGeometry(watched.rect())
        return False

    def start(self):
        self.animation.start()


def _carry_text(old, new):
    """Keep what was typed (and ticked) in the Login or Register form."""
    from PySide6.QtWidgets import QCheckBox, QLineEdit
    before, after = old.findChildren(QLineEdit), new.findChildren(QLineEdit)
    if len(before) == len(after):
        for source, target in zip(before, after):
            target.setText(source.text())
    before, after = old.findChildren(QCheckBox), new.findChildren(QCheckBox)
    if len(before) == len(after):
        for source, target in zip(before, after):
            target.setChecked(source.isChecked())


def _place_like(old, new):
    """Open `new` centred where `old` was, kept inside the screen.

    A full screen or maximized window keeps its state instead (adopt_state)."""
    if old.isFullScreen() or old.isMaximized():
        return
    screen = old.screen().availableGeometry()
    rect = new.geometry()
    rect.moveCenter(old.geometry().center())
    x = max(screen.left(), min(rect.left(), screen.right() - rect.width() + 1))
    y = max(screen.top(), min(rect.top(), screen.bottom() - rect.height() + 1))
    new.move(x, y)


def set_zoom(level):
    """Change the zoom and redraw the window on screen at the new size.

    Returns False (and changes nothing) if the user cancels, or a task is still
    running, so nothing in progress is lost."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from core import zoom
    from ui.theme import build_stylesheet

    old = _current
    if old is None or level == zoom.level():
        return True
    if _kind == "main":
        if old.task_running():
            QMessageBox.information(
                old, "Zoom", "A task is still running. Change the zoom when it finishes.")
            return False
        if not old.can_leave_page():          # an unsaved draft: asks first
            return False

    snapshot = old.grab()                     # what the user sees right now
    old.setUpdatesEnabled(False)              # no half-restyled flicker on the old window

    zoom.set_level(level)
    QApplication.instance().setStyleSheet(build_stylesheet())

    if _kind == "main":
        window = _make("main", old.pages.currentIndex())
        window.adopt_state(old)               # same full screen / maximized state
        old.logging_out = True                # closing it must not ask again
    else:
        window = _make(_kind)
        _carry_text(old, window)
    _place_like(old, window)

    _show(window, _kind)
    _Crossfade(window, snapshot).start()      # dissolve from the old picture
    return True