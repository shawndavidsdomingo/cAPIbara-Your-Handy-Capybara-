from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout

from ui import navigation
from core import session
from services.auth_service import verify_login
from core.zoom import px
from ui.widgets import (enable_zoom, fit_window, make_label, make_error_label,
                        make_input, make_button, make_logo, make_scroller)


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cAPIbara – Login")
        fit_window(self, 400, 600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)

        # One quiet card in the middle of the window
        card = QWidget()
        card.setObjectName("card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(make_scroller(card))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(6)

        self.username = make_input("Enter your username")
        self.password = make_input("Enter your password", password=True)
        self.username.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self.handle_login)
        self.error = make_error_label()
        self.error.setMinimumHeight(px(20))           # the form does not jump when an error shows

        layout.addWidget(make_logo(96))
        layout.addWidget(make_label("cAPIbara", "title", center=True))
        layout.addWidget(make_label("Your Handy Capybara", "muted", center=True))
        layout.addSpacing(22)
        layout.addWidget(make_label("Username", "fieldLabel"))
        layout.addWidget(self.username)
        layout.addSpacing(8)
        layout.addWidget(make_label("Password", "fieldLabel"))
        layout.addWidget(self.password)
        layout.addWidget(self.error)
        layout.addSpacing(4)
        layout.addWidget(make_button("Login", self.handle_login))
        layout.addStretch()
        layout.addWidget(make_label("New to cAPIbara?", "muted", center=True))
        layout.addWidget(make_button("Create an account", navigation.go_register,
                                     secondary=True))

        enable_zoom(self)
        self.username.setFocus()

    def handle_login(self):
        user = verify_login(self.username.text().strip(), self.password.text())
        if user is None:
            self.error.setText("Invalid username or password.")
            self.password.clear()
            self.password.setFocus()
            return
        session.login(user)
        navigation.go_main()