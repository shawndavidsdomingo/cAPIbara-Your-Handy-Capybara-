from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QListWidget, QStackedWidget, QLabel)

import navigation
import stats
from pages.dashboard_page import DashboardPage
from pages.url_page import UrlPage
from pages.msg_page import MessagePage
from pages.fake_page import FakeDataPage
from pages.profile_page import ProfilePage
from widgets import make_button


class MainWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.setWindowTitle("Utilities Hub")
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
        self.pages.addWidget(DashboardPage(username))
        self.pages.addWidget(UrlPage())
        self.pages.addWidget(MessagePage())
        self.pages.addWidget(FakeDataPage())
        self.pages.addWidget(ProfilePage(username))

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

    def closeEvent(self, event):
        # also asks about unsaved drafts when the window is closed
        if self.can_leave_page():
            event.accept()
        else:
            event.ignore()

    def logout(self):
        if self.can_leave_page():
            navigation.go_login()