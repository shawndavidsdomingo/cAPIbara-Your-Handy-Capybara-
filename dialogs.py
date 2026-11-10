"""Reusable pop-up dialogs shared by the Register window and Profile page.

GUI-only: no email is really sent. The OTP is generated locally and shown
in a 'demo' label so the flow can be tested without a mail server.
"""
import random

from PySide6.QtCore import Qt, QTimer, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton)

from auth_service import (email_taken, is_valid_email, mask_email,
                          update_password)

ERROR_STYLE = "color: #A3524A;"
MUTED_STYLE = "color: #6B6B68; font-size: 12px;"


def make_dialog_layout(dialog, title_text):
    """Shared dialog setup: modal, fixed width, bold title. Returns layout."""
    dialog.setModal(True)
    dialog.setFixedWidth(380)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(30, 24, 30, 24)
    layout.setSpacing(12)
    title = QLabel(title_text)
    title.setStyleSheet("font-size: 18px; font-weight: bold;")
    layout.addWidget(title)
    return layout


class OTPDialog(QDialog):
    """Asks for a 6-digit code 'sent' to an email. Accepted = code correct."""

    RESEND_SECONDS = 30

    def __init__(self, email, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verification")
        layout = make_dialog_layout(self, title)

        info = QLabel(f"We sent a 6-digit code to\n{mask_email(email)}")
        self.demo_hint = QLabel()          # shows the fake code
        self.demo_hint.setStyleSheet(MUTED_STYLE)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter 6-digit code")
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setStyleSheet("font-size: 20px;")
        self.code_input.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{0,6}")))
        self.code_input.returnPressed.connect(self.verify)

        self.error = QLabel("")
        self.error.setStyleSheet(ERROR_STYLE)
        self.error.setAlignment(Qt.AlignCenter)

        verify = QPushButton("Verify")
        verify.clicked.connect(self.verify)

        self.resend = QPushButton("Resend code")
        self.resend.setObjectName("secondary")
        self.resend.clicked.connect(self.send_code)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self.resend)
        row.addWidget(cancel)

        for w in (info, self.demo_hint, self.code_input, self.error, verify):
            layout.addWidget(w)
        layout.addLayout(row)

        # Countdown that keeps "Resend" disabled for a short time
        self.seconds_left = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

        self.send_code()

    def send_code(self):
        self.code = f"{random.randint(0, 999999):06d}"
        self.demo_hint.setText(f"Demo only: your code is {self.code}")
        self.code_input.clear()
        self.error.setText("")
        self.seconds_left = self.RESEND_SECONDS
        self.resend.setEnabled(False)
        self.update_resend_text()
        self.timer.start(1000)

    def tick(self):
        self.seconds_left -= 1
        if self.seconds_left <= 0:
            self.timer.stop()
            self.resend.setEnabled(True)
            self.resend.setText("Resend code")
        else:
            self.update_resend_text()

    def update_resend_text(self):
        self.resend.setText(f"Resend ({self.seconds_left}s)")

    def verify(self):
        entered = self.code_input.text()
        if len(entered) != 6:
            self.error.setText("Enter the 6-digit code.")
        elif entered != self.code:
            self.error.setText("Incorrect code. Try again.")
        else:
            self.timer.stop()
            self.accept()

    def done(self, result):
        self.timer.stop()          # never leave the timer running
        super().done(result)


def verify_otp(parent, email, title):
    """Shortcut: show the OTP dialog, return True if verified."""
    return OTPDialog(email, title, parent).exec() == QDialog.Accepted


class NewEmailDialog(QDialog):
    """Step 1 of changing email: type the new address."""

    def __init__(self, current_email, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Email")
        self.current_email = current_email
        self.email = ""
        layout = make_dialog_layout(self, "Change email")

        info = QLabel("Enter your new email. We will send a code to it.")
        info.setWordWrap(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("New email address")
        self.input.returnPressed.connect(self.submit)

        self.error = QLabel("")
        self.error.setStyleSheet(ERROR_STYLE)
        self.error.setAlignment(Qt.AlignCenter)

        send = QPushButton("Send code")
        send.clicked.connect(self.submit)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)

        for w in (info, self.input, self.error, send, cancel):
            layout.addWidget(w)

    def submit(self):
        new = self.input.text().strip()
        if not is_valid_email(new):
            self.error.setText("Please enter a valid email address.")
        elif new.lower() == self.current_email.lower():
            self.error.setText("That is already your current email.")
        elif email_taken(new):
            self.error.setText("That email is already in use.")
        else:
            self.email = new
            self.accept()


class NewPasswordDialog(QDialog):
    """Step 2 of changing password (shown only after the OTP is verified).
    The service checks the current password and saves the new salted hash."""

    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.user_id = user_id
        layout = make_dialog_layout(self, "Set new password")

        self.old = QLineEdit()
        self.old.setPlaceholderText("Current password")
        self.old.setEchoMode(QLineEdit.Password)

        self.new = QLineEdit()
        self.new.setPlaceholderText("New password (8+ characters)")
        self.new.setEchoMode(QLineEdit.Password)

        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("Confirm new password")
        self.confirm.setEchoMode(QLineEdit.Password)
        self.confirm.returnPressed.connect(self.submit)

        self.error = QLabel("")
        self.error.setStyleSheet(ERROR_STYLE)
        self.error.setAlignment(Qt.AlignCenter)
        self.error.setWordWrap(True)

        save = QPushButton("Save password")
        save.clicked.connect(self.submit)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)

        for w in (self.old, self.new, self.confirm, self.error, save, cancel):
            layout.addWidget(w)

    def submit(self):
        old, new, confirm = self.old.text(), self.new.text(), self.confirm.text()
        if not old:
            self.error.setText("Enter your current password.")
        elif len(new) < 8:
            self.error.setText("Password must be at least 8 characters.")
        elif new != confirm:
            self.error.setText("Passwords do not match.")
        else:
            try:
                update_password(self.user_id, old, new)
            except ValueError as error:
                self.error.setText(str(error))
            else:
                self.accept()


class SentDialog(QDialog):
    """Modal shown after an SMS or Email is 'sent'."""

    def __init__(self, kind, recipient, preview, time, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{kind} Sent")
        layout = make_dialog_layout(self, f"{kind} sent")

        to = QLabel(f"To: {recipient or 'No recipient'}")
        to.setObjectName("bold")
        to.setWordWrap(True)

        body = QLabel(preview if len(preview) <= 80 else preview[:80] + "...")
        body.setWordWrap(True)

        info = QLabel(f"Sent at {time}")
        info.setStyleSheet(MUTED_STYLE)

        demo = QLabel("Demo only: nothing was actually sent.")
        demo.setStyleSheet(MUTED_STYLE)

        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)

        for w in (to, body, info, demo, ok):
            layout.addWidget(w)