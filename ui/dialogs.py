"""Reusable pop-up dialogs shared by the Register window and Profile page.

The OTP is generated locally and emailed through Brevo (message_service). If no
BREVO_API_KEY is set, the dialog stays in demo mode and shows the code on
screen, so the flow can still be tested without a mail account.

Colours and fonts come from theme.py through object names ("heading", "muted",
"error", "fieldLabel", "secondary", ...), so nothing here sets its own colours.
"""
import random

from PySide6.QtCore import (Qt, QTimer, QRegularExpression, QRectF,
                            QPropertyAnimation)
from PySide6.QtGui import QRegularExpressionValidator, QPainter, QPen, QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QPushButton, QTextEdit,
                               QWidget)

from services import contact_service, message_service
from ui.theme import COLORS
from services.auth_service import (email_taken, is_valid_email, mask_email,
                          update_password)
from services.message_service import SendError
from ui.widgets import make_button, make_error_label, make_input, make_label
from ui.workers import Task


def make_dialog_layout(dialog, title_text, center=False):
    """Shared dialog setup: modal, fixed width, heading. Returns the layout."""
    dialog.setModal(True)
    dialog.setFixedWidth(380)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(30, 26, 30, 26)
    layout.setSpacing(8)
    title = make_label(title_text, "heading", center=center)
    title.setWordWrap(True)
    layout.addWidget(title)
    layout.addSpacing(4)
    return layout


def quiet(text, center=False):
    """A small muted line that wraps."""
    label = make_label(text, "muted", center=center)
    label.setWordWrap(True)
    return label


def error_line():
    """The red message line. It keeps its height, so the dialog does not jump."""
    label = make_error_label()
    label.setMinimumHeight(20)
    return label


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

        info = make_label(f"We sent a 6-digit code to\n{mask_email(email)}")
        info.setWordWrap(True)
        self.demo_hint = quiet("", center=True)          # shows the fake code

        self.code_input = QLineEdit()
        self.code_input.setObjectName("otp")             # big digits, see theme.py
        self.code_input.setPlaceholderText("Enter 6-digit code")
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{0,6}")))
        self.code_input.returnPressed.connect(self.verify)

        self.error = error_line()

        verify = make_button("Verify", self.verify)

        self.resend = make_button("Resend code", self.send_code, secondary=True)
        cancel = make_button("Cancel", self.reject, secondary=True)

        row = QHBoxLayout()
        row.addWidget(self.resend)
        row.addWidget(cancel)

        layout.addWidget(info)
        layout.addSpacing(6)
        layout.addWidget(self.code_input)
        layout.addWidget(self.demo_hint)
        layout.addWidget(self.error)
        layout.addWidget(verify)
        layout.addLayout(row)

        # Countdown that keeps "Resend" disabled for a short time
        self.seconds_left = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

        self.send_code()
        self.code_input.setFocus()

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

        info = quiet("Enter your new email. We will send a code to it.")

        self.input = make_input("New email address")
        self.input.returnPressed.connect(self.submit)

        self.error = error_line()

        layout.addWidget(info)
        layout.addSpacing(6)
        layout.addWidget(make_label("New email", "fieldLabel"))
        layout.addWidget(self.input)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Send code", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.input.setFocus()

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

        self.old = make_input("Current password", password=True)
        self.new = make_input("New password (8+ characters)", password=True)
        self.confirm = make_input("Confirm new password", password=True)
        self.old.returnPressed.connect(self.new.setFocus)
        self.new.returnPressed.connect(self.confirm.setFocus)
        self.confirm.returnPressed.connect(self.submit)

        self.error = error_line()

        for text, field in (("Current password", self.old),
                            ("New password", self.new),
                            ("Confirm new password", self.confirm)):
            layout.addWidget(make_label(text, "fieldLabel"))
            layout.addWidget(field)
            layout.addSpacing(4)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Save password", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.old.setFocus()

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


class ContactDialog(QDialog):
    """Add a contact, or edit one when `contact` is given.
    The service checks and saves it; the dialog only shows its message."""

    def __init__(self, user_id, contact=None, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.contact = contact
        self.setWindowTitle("Edit Contact" if contact else "Add Contact")
        layout = make_dialog_layout(self, "Edit contact" if contact else "New contact")

        self.name = make_input("Full name")
        self.mobile = make_input("Mobile number (09XXXXXXXXX)")
        self.email = make_input("Email address")
        if contact:
            self.name.setText(contact["name"])
            self.mobile.setText(contact["mobile"])
            self.email.setText(contact["email"])
        self.name.returnPressed.connect(self.mobile.setFocus)
        self.mobile.returnPressed.connect(self.email.setFocus)
        self.email.returnPressed.connect(self.submit)

        self.error = error_line()

        layout.addWidget(quiet("Add a mobile number, an email address, or both."))
        layout.addSpacing(4)
        for text, field in (("Name", self.name), ("Mobile number", self.mobile),
                            ("Email", self.email)):
            layout.addWidget(make_label(text, "fieldLabel"))
            layout.addWidget(field)
            layout.addSpacing(4)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Save contact", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.name.setFocus()

    def submit(self):
        name, mobile, email = (self.name.text(), self.mobile.text(),
                               self.email.text())
        try:
            if self.contact:
                contact_service.update_contact(
                    self.user_id, self.contact["id"], name, mobile, email)
            else:
                contact_service.add_contact(self.user_id, name, mobile, email)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.accept()


class ContactPickerDialog(QDialog):
    """Pick one contact for an SMS (need="mobile") or an Email (need="email").
    Only contacts that have that kind of detail are listed. After Accepted,
    `value` holds the chosen number or address."""

    def __init__(self, user_id, need, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a Contact")
        self.need = need
        self.value = ""
        self.shown = []
        layout = make_dialog_layout(self, "Choose a contact")

        what = "mobile number" if need == "mobile" else "email address"
        self.contacts = contact_service.filter_contacts(
            contact_service.get_contacts(user_id), need=need)
        if not self.contacts:
            layout.addWidget(quiet(f"You have no contacts with a {what} yet. "
                                   "Add some on the Contacts page."))
            layout.addSpacing(6)
            layout.addWidget(make_button("Close", self.reject, secondary=True))
            return

        self.search = make_input("Search by name or " + what)
        self.search.textChanged.connect(self.fill)
        self.search.returnPressed.connect(self.choose)
        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.list.itemDoubleClicked.connect(lambda _item: self.choose())

        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addSpacing(4)
        layout.addWidget(make_button("Select", self.choose))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.fill()
        self.search.setFocus()

    def fill(self):
        self.shown = contact_service.filter_contacts(
            self.contacts, self.search.text(), need=self.need)
        self.list.clear()
        for contact in self.shown:
            self.list.addItem(f"{contact['name']}  -  {contact[self.need]}")
        if self.shown:
            self.list.setCurrentRow(0)

    def choose(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.shown):
            self.value = self.shown[row][self.need]
            self.accept()


class SentDialog(QDialog):
    """Modal shown after an SMS or Email is 'sent'."""

    def __init__(self, kind, recipient, preview, time, parent=None, demo=True):
        super().__init__(parent)
        self.setWindowTitle(f"{kind} Sent")
        layout = make_dialog_layout(self, f"{kind} sent", center=True)

        badge = make_label("\u2713", "successBadge", center=True)     # a check mark
        badge.setFixedSize(44, 44)
        layout.insertWidget(0, badge, 0, Qt.AlignHCenter)

        to = make_label(f"To: {recipient or 'No recipient'}", "bold", center=True)
        to.setWordWrap(True)

        body = make_label(preview if len(preview) <= 80 else preview[:80] + "...",
                          center=True)
        body.setWordWrap(True)

        layout.addWidget(to)
        layout.addWidget(body)
        layout.addSpacing(4)
        layout.addWidget(quiet(f"Sent at {time}", center=True))
        if demo:
            layout.addWidget(quiet("Demo only: nothing was actually sent.", center=True))
        layout.addSpacing(8)
        layout.addWidget(make_button("OK", self.accept))


class MessageDialog(QDialog):
    """Read-only view of a message from the Sent list (recipient, subject, text)."""

    def __init__(self, kind, recipient, subject, body, time, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sent {kind}")
        layout = make_dialog_layout(self, subject or f"Sent {kind}")
        self.setFixedWidth(520)

        to = make_label(f"To: {recipient or 'No recipient'}", "bold")
        to.setWordWrap(True)
        to.setTextInteractionFlags(Qt.TextSelectableByMouse)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(body)
        text.setMinimumHeight(180)

        layout.addWidget(to)
        layout.addWidget(quiet(f"Sent {time}"))
        layout.addSpacing(4)
        layout.addWidget(text)
        layout.addSpacing(6)
        layout.addWidget(make_button("Close", self.accept))


class Spinner(QWidget):
    """A ring with a moving arc. Draws itself, so it needs no image or GIF."""

    TRACK = QColor(COLORS["border"])
    ARC = QColor(COLORS["primary"])

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
        self.setStyleSheet(
            f"QDialog#sendingModal {{ border: 1px solid {COLORS['border_strong']}; }}")
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