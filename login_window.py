from PySide6.QtWidgets import QWidget, QVBoxLayout

import navigation
import session
from auth_service import verify_login
from widgets import make_label, make_error_label, make_input, make_button


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cAPIbara – Login")
        self.setFixedSize(360, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        self.username = make_input("Username")
        self.password = make_input("Password", password=True)
        self.password.returnPressed.connect(self.handle_login)
        self.error = make_error_label()

        for w in (make_label("cAPIbara", "title", center=True),
                  make_label("Your Handy Capybara", "muted", center=True),
                  self.username, self.password, self.error,
                  make_button("Login", self.handle_login),
                  make_button("Create an account", navigation.go_register,
                              secondary=True)):
            layout.addWidget(w)

    def handle_login(self):
        user = verify_login(self.username.text().strip(), self.password.text())
        if user is None:
            self.error.setText("Invalid username or password.")
            return
        session.login(user)
        navigation.go_main()
