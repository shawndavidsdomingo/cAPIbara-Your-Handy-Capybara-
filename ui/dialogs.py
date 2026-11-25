"""Reusable pop-up dialogs shared by the Register window and Profile page.

The OTP is generated locally and emailed through Brevo (message_service). If no
BREVO_API_KEY is set, the dialog stays in demo mode and shows the code on
screen, so the flow can still be tested without a mail account.
"""
import random

from PySide6.QtCore import (Qt, QTimer, QRegularExpression, QRectF,
                            QPropertyAnimation)
from PySide6.QtGui import QRegularExpressionValidator, QPainter, QPen, QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QWidget)

from services import message_service
from services.auth_service import (email_taken, is_valid_email, mask_email,
                          update_password)
from services.message_service import SendError
from ui.workers import Task

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
        self.email = email
        self.code = None
        self.task = None           # the background email send, if any
        self.closed = False        # set when the dialog ends; late replies are ignored
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
        if self.task is not None:          # a code is already being sent
            return
        self.code = f"{random.randint(0, 999999):06d}"
        self.code_input.clear()
        self.error.setText("")
        self.resend.setEnabled(False)

        if not message_service.email_enabled():       # demo mode: show the code
            self.demo_hint.setText(f"Demo only: your code is {self.code}")
            self.start_countdown()
            return

        self.demo_hint.setText("Sending the code...")
        self.resend.setText("Sending...")
        self.task = Task(message_service.send_otp_email, self.email, self.code,
                         safe=(SendError,))
        self.task.succeeded.connect(self.on_code_sent)
        self.task.failed.connect(self.on_code_failed)
        self.task.finished.connect(self.clear_task)
        self.task.start()

    def on_code_sent(self, _result):
        if self.closed:
            return
        self.demo_hint.setText("Check your inbox (and the spam folder).")
        self.start_countdown()

    def on_code_failed(self, message):
        if self.closed:
            return
        self.code = None                   # that code never reached the user
        self.demo_hint.setText("")
        self.error.setText(message)
        self.resend.setEnabled(True)
        self.resend.setText("Resend code")

    def clear_task(self):
        self.task = None

    def start_countdown(self):
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
        elif self.code is None:
            self.error.setText("No code was sent. Press Resend code.")
        elif entered != self.code:
            self.error.setText("Incorrect code. Try again.")
        else:
            self.timer.stop()
            self.accept()

    def done(self, result):
        self.closed = True
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

    def __init__(self, kind, recipient, preview, time, parent=None, demo=True):
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

        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)

        widgets = [to, body, info]
        if demo:
            note = QLabel("Demo only: nothing was actually sent.")
            note.setStyleSheet(MUTED_STYLE)
            widgets.append(note)
        widgets.append(ok)
        for w in widgets:
            layout.addWidget(w)


class MessageDialog(QDialog):
    """Read-only view of a message from the Sent list (recipient, subject, text)."""

    def __init__(self, kind, recipient, subject, body, time, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sent {kind}")
        layout = make_dialog_layout(self, subject or f"Sent {kind}")
        self.setFixedWidth(520)

        to = QLabel(f"To: {recipient or 'No recipient'}")
        to.setObjectName("bold")
        to.setWordWrap(True)
        to.setTextInteractionFlags(Qt.TextSelectableByMouse)

        info = QLabel(f"Sent {time}")
        info.setStyleSheet(MUTED_STYLE)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(body)
        text.setMinimumHeight(180)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        for w in (to, info, text, close):
            layout.addWidget(w)


class Spinner(QWidget):
    """A ring with a moving arc. Draws itself, so it needs no image or GIF."""

    TRACK = QColor("#D6D5D0")
    ARC = QColor("#4A4F57")

    def __init__(self, size=52):
        super().__init__()
        self.setFixedSize(size, size)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)                 # about 60 frames a second
        self.timer.timeout.connect(self.step)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def step(self):
        self.angle = (self.angle + 6) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(5, 5, self.width() - 10, self.height() - 10)
        pen = QPen(self.TRACK, 5)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        pen.setColor(self.ARC)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, -self.angle * 16, -100 * 16)    # 1/16 degree units


class SendingDialog(QDialog):
    """Modal "please wait" pop-up shown while a message is on its way.

    The page opens it with start() and closes it with finish(). The user cannot
    close it (Esc and Alt+F4 are ignored), because the send must not be repeated.
    `status_text(seconds)` gives the line under the title, so the page decides
    what it says as time passes."""

    def __init__(self, title, status_text, parent=None):
        super().__init__(parent)
        self.setObjectName("sendingModal")
        self.setStyleSheet("QDialog#sendingModal { border: 1px solid #D6D5D0; }")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(300)
        self.status_text = status_text
        self.ticks = 0
        self.finishing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 26)
        layout.setSpacing(12)
        self.spinner = Spinner()
        heading = QLabel(title)
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignCenter)
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        hint = QLabel("Please keep the app open.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.spinner, 0, Qt.AlignHCenter)
        for w in (heading, self.status, hint):
            layout.addWidget(w)

        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.tick)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(180)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)

    def tick(self):
        seconds = self.ticks * self.timer.interval() / 1000
        dots = "." * (self.ticks % 4)
        self.status.setText(f"{self.status_text(seconds)}{dots:<3}  ({int(seconds)}s)")
        self.ticks += 1

    def start(self):
        """Show it centred over its window and fade it in (does not block)."""
        self.tick()
        self.timer.start()
        self.spinner.start()
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            self.move(parent.geometry().center() - self.rect().center())
        self.setWindowOpacity(0.0)
        self.show()
        self.fade.start()

    def finish(self):
        self.finishing = True
        self.timer.stop()
        self.spinner.stop()
        self.fade.stop()
        self.hide()
        self.deleteLater()

    def reject(self):                 # Esc does nothing
        pass

    def closeEvent(self, event):
        if self.finishing:
            super().closeEvent(event)
        else:
            event.ignore()