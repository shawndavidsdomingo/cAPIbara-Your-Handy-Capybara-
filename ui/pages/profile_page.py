from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QDialog)

from core import session
from services.auth_service import update_email, update_name
from ui.dialogs import NewEmailDialog, NewPasswordDialog, verify_otp
from ui.widgets import make_button, make_label

OK_COLOR = "#5B7F5E"
ERR_COLOR = "#A3524A"


class ProfilePage(QWidget):
    """Update name, change email (OTP to NEW email),
    change password (OTP to CURRENT email). Saved through auth_service."""

    def __init__(self):
        super().__init__()
        self.user = session.current()           # the logged-in user's dict
        username = self.user["username"]

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignTop)

        card = QWidget()
        card.setMaximumWidth(460)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(make_label("Profile", "heading"))
        layout.addWidget(QLabel(f"Username: {username}"))

        # --- Name ---
        layout.addWidget(QLabel("Full name"))
        self.name = QLineEdit(self.user["full_name"])
        layout.addWidget(self.name)
        layout.addWidget(make_button("Save name", self.save_name))

        # --- Email (read-only; changed through the OTP flow) ---
        layout.addWidget(QLabel("Email"))
        self.email = QLineEdit(self.user["email"])
        self.email.setReadOnly(True)
        email_row = QHBoxLayout()
        email_row.addWidget(self.email, 1)
        email_row.addWidget(make_button("Change email", self.change_email,
                                        secondary=True))
        layout.addLayout(email_row)

        # --- Password ---
        layout.addWidget(QLabel("Password"))
        layout.addWidget(make_button("Change password", self.change_password,
                                     secondary=True))

        # --- Status message ---
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        outer.addWidget(card)

    def show_status(self, text, ok=True):
        color = OK_COLOR if ok else ERR_COLOR
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(text)

    # ---- Name ----

    def save_name(self):
        new = self.name.text().strip()
        if not new:
            self.show_status("Name cannot be empty.", ok=False)
        elif new == self.user["full_name"]:
            self.show_status("No changes to save.", ok=False)
        else:
            try:
                update_name(self.user["id"], new)
            except ValueError as error:
                self.show_status(str(error), ok=False)
                return
            self.user["full_name"] = new
            self.show_status("Name updated.")

    # ---- Email: new address -> OTP sent to the NEW email ----

    def change_email(self):
        dialog = NewEmailDialog(self.user["email"], self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_email = dialog.email

        if verify_otp(self, new_email, "Confirm your new email"):
            try:
                update_email(self.user["id"], new_email)
            except ValueError as error:
                self.show_status(str(error), ok=False)
                return
            self.user["email"] = new_email
            self.email.setText(new_email)
            self.show_status("Email updated.")
        else:
            self.show_status("Email was not changed.", ok=False)

    # ---- Password: OTP sent to the CURRENT email -> new password ----

    def change_password(self):
        if not verify_otp(self, self.user["email"], "Confirm it's you"):
            self.show_status("Password was not changed.", ok=False)
            return

        dialog = NewPasswordDialog(self.user["id"], self)
        if dialog.exec() == QDialog.Accepted:
            self.show_status("Password updated.")
        else:
            self.show_status("Password was not changed.", ok=False)