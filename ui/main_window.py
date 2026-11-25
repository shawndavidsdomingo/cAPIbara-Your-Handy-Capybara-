from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QListWidget, QStackedWidget,
                               QApplication, QMessageBox)

from ui import navigation
from core import session
from ui.pages.dashboard_page import DashboardPage
from ui.pages.url_page import UrlPage
from ui.pages.msg_page import MessagePage
from ui.pages.contacts_page import ContactsPage
from ui.pages.fake_page import FakeDataPage
from ui.pages.profile_page import ProfilePage
from core.zoom import px
from ui.widgets import enable_zoom, make_button, make_label, make_logo


class MainWindow(QMainWindow):
    MAX_CONTENT_WIDTH = 1500

    def __init__(self, start_page=0):
        super().__init__()
        self.logging_out = False   # logout closes this window without asking
        self.was_maximized = False # what to go back to when leaving full screen
        username = session.current()["username"]
        self.setWindowTitle("cAPIbara: Your Handy Capybara")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar: brand on top, menu in the middle, account and logout at the bottom
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(px(230))
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 20, 16, 16)
        side.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(make_label("cAPIbara", "heading"))
        names.addWidget(make_label("Your Handy Capybara", "muted"))
        brand.addWidget(make_logo(38))
        brand.addLayout(names, 1)
        side.addLayout(brand)
        side.addSpacing(18)

        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.menu.addItems(["Dashboard", "URL Shortening", "SMS and Email",
                            "Contacts", "Fake Data", "Profile"])
        side.addWidget(self.menu, 1)

        side.addSpacing(8)
        who = make_label(session.current()["full_name"], "bold")
        who.setWordWrap(True)
        side.addWidget(who)
        side.addWidget(make_label(f"@{username}", "muted"))
        side.addSpacing(8)
        self.fullscreen_button = make_button("Full screen", self.toggle_fullscreen,
                                             secondary=True)
        self.fullscreen_button.setToolTip("Press F11 to switch, Esc to leave")
        side.addWidget(self.fullscreen_button)
        side.addWidget(make_button("Logout", self.logout, secondary=True))

        # F11 switches full screen on and off; Esc leaves it
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=self.leave_fullscreen)
        enable_zoom(self)                   # Ctrl + mouse wheel (and Ctrl and +, -, 0)

        # Pages (same order as the menu items)
        self.pages = QStackedWidget()
        self.pages.addWidget(DashboardPage())
        self.pages.addWidget(UrlPage())
        self.pages.addWidget(MessagePage())
        self.pages.addWidget(ContactsPage())
        self.pages.addWidget(FakeDataPage())
        self.pages.addWidget(ProfilePage())

        self.menu.currentRowChanged.connect(self.change_page)
        self.menu.setCurrentRow(start_page)  # also sizes the window (see change_page)

        # The pages sit in a padded area to the right of the sidebar
        # On a big screen the pages stop growing at MAX_CONTENT_WIDTH and stay
        # centred, so full screen looks tidy instead of stretched.
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 24)
        self.pages.setMaximumWidth(px(self.MAX_CONTENT_WIDTH))
        content_layout.addStretch(1)
        content_layout.addWidget(self.pages, 1000)
        content_layout.addStretch(1)

        root.addWidget(sidebar)
        root.addWidget(content, 1)

    def can_leave_page(self):
        # a page with unsaved work (SMS/Email drafts) asks the user first
        page = self.pages.currentWidget()
        return not hasattr(page, "confirm_leave") or page.confirm_leave()

    def change_page(self, index):
        if not self.can_leave_page():
            # user cancelled: put the sidebar selection back
            self.menu.blockSignals(True)
            self.menu.setCurrentRow(self.pages.currentIndex())
            self.menu.blockSignals(False)
            return
        self.pages.setCurrentIndex(index)
        page = self.pages.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()          # dashboard reloads its numbers
        self.resize_for(page)

    def resize_for(self, page):
        """A page with `wide = True` (Fake Data: 10 columns + history list)
        gets a bigger window. Never bigger than the screen."""
        if self.isFullScreen() or self.isMaximized():
            return                  # the user chose the size: leave it alone
        width, height = (1440, 700) if getattr(page, "wide", False) else (1000, 660)
        width, height = px(width), px(height)
        screen = self.screen().availableGeometry()
        self.resize(min(width, screen.width()), min(height, screen.height()))

    # ---------- Full screen ----------

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.was_maximized = self.isMaximized()
            self.showFullScreen()
        self.sync_fullscreen_button()

    def leave_fullscreen(self):
        if self.isFullScreen():
            if self.was_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        self.sync_fullscreen_button()

    def sync_fullscreen_button(self):
        self.fullscreen_button.setText(
            "Exit full screen" if self.isFullScreen() else "Full screen")

    def changeEvent(self, event):
        super().changeEvent(event)
        # the window manager can also switch full screen (for example the green
        # button on a Mac), so keep the label right in that case too
        if event.type() == QEvent.WindowStateChange and hasattr(self, "fullscreen_button"):
            self.sync_fullscreen_button()

    def adopt_state(self, old):
        """Open in the same state (full screen or maximized) as the window this
        one replaces. Used when the zoom changes. Call it before show()."""
        if old.isFullScreen():
            self.was_maximized = old.was_maximized
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)
        elif old.isMaximized():
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
        self.sync_fullscreen_button()

    # ---------- Closing the app ----------

    def all_pages(self):
        return [self.pages.widget(i) for i in range(self.pages.count())]

    def task_running(self):
        """True if any page is busy (a page opts in by defining is_busy())."""
        return any(hasattr(page, "is_busy") and page.is_busy()
                   for page in self.all_pages())

    def confirm_close(self):
        text = "Are you sure you want to close the app?"
        if self.task_running():
            text += ("\n\nA task is still running. "
                     "The app will close as soon as it finishes.")
        answer = QMessageBox.question(
            self, "Close cAPIbara", text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def finish_running_tasks(self):
        """Wait for running work (a page opts in by defining shutdown())."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for page in self.all_pages():
                if hasattr(page, "shutdown"):
                    page.shutdown()
        finally:
            QApplication.restoreOverrideCursor()

    def closeEvent(self, event):
        # 1. ask (not when logging out), 2. unsaved drafts, 3. let work finish
        if not self.logging_out and not self.confirm_close():
            event.ignore()
        elif not self.can_leave_page():
            event.ignore()
        else:
            self.finish_running_tasks()
            event.accept()

    def confirm_logout(self):
        answer = QMessageBox.question(
            self, "Log out", "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def logout(self):
        if self.confirm_logout() and self.can_leave_page():
            self.logging_out = True
            navigation.go_login()      # closes this window (finishing running work)
            session.logout()           # cleared last, so that work can still save