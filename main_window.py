from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QListWidget, QStackedWidget, QLabel,
                               QApplication, QMessageBox)

import navigation
import session
import stats
from pages.dashboard_page import DashboardPage
from pages.url_page import UrlPage
from pages.msg_page import MessagePage
from pages.fake_page import FakeDataPage
from pages.profile_page import ProfilePage
from widgets import make_button


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logging_out = False   # logout closes this window without asking
        username = session.current()["username"]
        self.setWindowTitle("cAPIbara: Your Handy Capybara")
        stats.reset()      # fresh totals for each login

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Sidebar
        side = QVBoxLayout()
        side.addWidget(QLabel(f"Logged in as: {username}"))
        self.menu = QListWidget()
        self.menu.addItems(["Dashboard", "URL Shortening", "SMS and Email",
                            "Fake Data", "Profile"])
        self.menu.setFixedWidth(180)
        side.addWidget(self.menu)
        side.addWidget(make_button("Logout", self.logout))

        # Pages (same order as the menu items)
        self.pages = QStackedWidget()
        self.pages.addWidget(DashboardPage())
        self.pages.addWidget(UrlPage())
        self.pages.addWidget(MessagePage())
        self.pages.addWidget(FakeDataPage())
        self.pages.addWidget(ProfilePage())

        self.menu.currentRowChanged.connect(self.change_page)
        self.menu.setCurrentRow(0)          # also sizes the window (see change_page)

        root.addLayout(side)
        root.addWidget(self.pages, 1)

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
        width, height = (1400, 650) if getattr(page, "wide", False) else (900, 600)
        screen = self.screen().availableGeometry()
        self.resize(min(width, screen.width()), min(height, screen.height()))

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

    def logout(self):
        if self.can_leave_page():
            self.logging_out = True
            navigation.go_login()      # closes this window (finishing running work)
            session.logout()           # cleared last, so that work can still save