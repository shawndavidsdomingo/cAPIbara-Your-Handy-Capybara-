from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QMessageBox, QVBoxLayout, QWidget)

from ui import navigation
from services.auth_service import (email_taken, is_valid_email, is_valid_username,
                          register_user, username_taken)
from ui.dialogs import verify_otp
from ui.terms_dialog import TermsDialog
from core.zoom import px
from ui.theme import COLORS
from ui.widgets import (enable_zoom, fit_window, make_label, make_error_label,
                        make_input, make_button, make_logo, make_scroller)


class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cAPIbara – Register")
        fit_window(self, 400, 800)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)

        # Same quiet card as the Login window
        card = QWidget()
        card.setObjectName("card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(make_scroller(card))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(4)

        self.full_name = make_input("Enter your full name")
        self.email = make_input("Enter your email")
        self.username = make_input("Choose a username")
        self.password = make_input("At least 8 characters", password=True)
        self.confirm = make_input("Re-enter your password", password=True)
        self.error = make_error_label()
        self.error.setMinimumHeight(px(20))           # the form does not jump when an error shows

        # Terms and Conditions: tick the box, or read them and press "I agree"
        self.terms = QCheckBox("I agree to the")
        self.terms_link = QLabel(
            f'<a href="terms" style="color:{COLORS["primary"]}">Terms and Conditions</a>')
        self.terms_link.setTextFormat(Qt.RichText)
        self.terms_link.setCursor(Qt.PointingHandCursor)
        self.terms_link.linkActivated.connect(lambda _link: self.open_terms())
        terms_row = QHBoxLayout()
        terms_row.setSpacing(4)
        terms_row.addWidget(self.terms)
        terms_row.addWidget(self.terms_link)
        terms_row.addStretch()

        # Enter moves to the next field; Enter on the last one registers
        fields = (self.full_name, self.email, self.username, self.password, self.confirm)
        for current, following in zip(fields, fields[1:]):
            current.returnPressed.connect(following.setFocus)
        self.confirm.returnPressed.connect(self.handle_register)

        layout.addWidget(make_logo(64))
        layout.addWidget(make_label("Create Account", "title", center=True))
        layout.addWidget(make_label("It only takes a minute", "muted", center=True))
        layout.addSpacing(14)
        for text, field in (("Full name", self.full_name), ("Email", self.email),
                            ("Username", self.username), ("Password", self.password),
                            ("Confirm password", self.confirm)):
            layout.addWidget(make_label(text, "fieldLabel"))
            layout.addWidget(field)
            layout.addSpacing(6)
        layout.addSpacing(4)
        layout.addLayout(terms_row)
        layout.addWidget(self.error)
        layout.addSpacing(2)
        layout.addWidget(make_button("Register", self.handle_register))
        layout.addStretch()
        layout.addWidget(make_label("Already have an account?", "muted", center=True))
        layout.addWidget(make_button("Back to Login", navigation.go_login,
                                     secondary=True))

        enable_zoom(self)
        self.full_name.setFocus()

    def open_terms(self):
        if TermsDialog(self).exec() == QDialog.Accepted:
            self.terms.setChecked(True)               # "I agree" ticks the box for them

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
        elif not self.terms.isChecked():
            self.error.setText("Please accept the Terms and Conditions to continue.")
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