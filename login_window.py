from PySide6.QtWidgets import QWidget, QVBoxLayout

import navigation
from demo_store import check_login   # temporary, replaced by SQLite later
from widgets import make_label, make_error_label, make_input, make_button


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Utilities Hub - Login")
        self.setFixedSize(360, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        self.username = make_input("Username")
        self.password = make_input("Password", password=True)
        self.password.returnPressed.connect(self.handle_login)
        self.error = make_error_label()

        for w in (make_label("Utilities Hub", "title", center=True),
                  self.username, self.password, self.error,
                  make_button("Login", self.handle_login),
                  make_button("Create an account", navigation.go_register,
                              secondary=True)):
            layout.addWidget(w)

    def handle_login(self):
        username = self.username.text().strip()
        if check_login(username, self.password.text()):
            navigation.go_main(username)
        else:
            self.error.setText("Invalid username or password.")