from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox

from ui import navigation
from services.auth_service import (email_taken, is_valid_email, is_valid_username,
                          register_user, username_taken)
from ui.dialogs import verify_otp
from ui.widgets import make_label, make_error_label, make_input, make_button


class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cAPIbara – Register")
        self.setFixedSize(360, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        self.full_name = make_input("Full name")
        self.email = make_input("Email")
        self.username = make_input("Username")
        self.password = make_input("Password (8+ characters)", password=True)
        self.confirm = make_input("Confirm password", password=True)
        self.confirm.returnPressed.connect(self.handle_register)
        self.error = make_error_label()

        for w in (make_label("Create Account", "title", center=True),
                  self.full_name, self.email, self.username,
                  self.password, self.confirm, self.error,
                  make_button("Register", self.handle_register),
                  make_button("Back to Login", navigation.go_login,
                              secondary=True)):
            layout.addWidget(w)

    def handle_register(self):
        name = self.full_name.text().strip()
        email = self.email.text().strip()
        username = self.username.text().strip()
        password = self.password.text()

        if not all((name, email, username, password, self.confirm.text())):
            self.error.setText("Please fill in all fields.")
        elif not is_valid_email(email):
            self.error.setText("Please enter a valid email address.")
        elif not is_valid_username(username):
            self.error.setText(
                "Username must be 3-20 letters, numbers or underscores.")
        elif username_taken(username):
            self.error.setText("That username is already taken.")
        elif email_taken(email):
            self.error.setText("That email is already registered.")
        elif len(password) < 8:
            self.error.setText("Password must be at least 8 characters.")
        elif password != self.confirm.text():
            self.error.setText("Passwords do not match.")
        elif not verify_otp(self, email, "Verify your email"):
            self.error.setText("Email not verified. Account not created.")
        else:
            self.create_account(name, email, username, password)

    def create_account(self, name, email, username, password):
        # The account is only created AFTER the OTP is verified
        try:
            register_user(username, name, email, password)
        except ValueError as error:
            self.error.setText(str(error))
            return
        QMessageBox.information(
            self, "Register", "Account created. You can now log in.")
        navigation.go_login()
