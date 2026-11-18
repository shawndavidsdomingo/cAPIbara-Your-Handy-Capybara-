import logging
import sqlite3
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QMessageBox, QApplication
)

import message_service
import session
from auth_service import is_valid_email
from dialogs import MessageDialog, SentDialog
from message_service import SendError
from workers import Task
from widgets import make_label

log = logging.getLogger(__name__)


def local_stamp(stamp):
    """SQLite stores UTC. Show it in the computer's own time zone."""
    try:
        utc = datetime.strptime(stamp[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return utc.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return stamp or ""


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class DraftTab(QWidget):
    """Shared draft and sent message logic. Drafts and sent messages are kept
    in the database (message_service), so they survive a restart."""

    kind = ""

    def __init__(self):
        super().__init__()

        self.user = session.current()   # the logged-in user's dict
        self.drafts = []        # each: {"id", "data", "time"}
        self.sent = []          # same shape, newest first
        self.current = -1
        self.task = None        # the background send in progress, if any
        self.pending = None     # the message being sent by that task

        layout = QHBoxLayout(self)

        # Left: Message form
        left = QVBoxLayout()
        self.form = self.build_form()
        left.addWidget(self.form)

        buttons = QHBoxLayout()

        self.save_button = QPushButton("Save Draft")
        self.save_button.clicked.connect(self.save_draft)

        self.send_button = QPushButton(f"Send {self.kind}")
        self.send_button.clicked.connect(self.send)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.send_button)

        left.addLayout(buttons)

        # Right: Drafts and Sent tabs
        right = QVBoxLayout()

        self.message_tabs = QTabWidget()

        # Drafts tab
        draft_page = QWidget()
        draft_layout = QVBoxLayout(draft_page)

        self.draft_list = QListWidget()
        self.draft_list.currentRowChanged.connect(
            self.load_draft
        )

        self.delete_button = QPushButton("Delete Draft")
        self.delete_button.setObjectName("secondary")
        self.delete_button.clicked.connect(self.delete_draft)

        draft_layout.addWidget(self.draft_list)
        draft_layout.addWidget(self.delete_button)

        # Sent tab
        sent_page = QWidget()
        sent_layout = QVBoxLayout(sent_page)

        self.sent_list = QListWidget()
        self.sent_list.setToolTip("Double-click to open")
        self.sent_list.itemDoubleClicked.connect(self.view_sent)

        self.open_button = QPushButton("Open")
        self.open_button.setObjectName("secondary")
        self.open_button.clicked.connect(self.view_sent)

        sent_layout.addWidget(self.sent_list)
        sent_layout.addWidget(make_label("Double-click a message to open it.", "muted"))
        sent_layout.addWidget(self.open_button)

        self.message_tabs.addTab(draft_page, "Drafts")
        self.message_tabs.addTab(sent_page, "Sent")

        right.addWidget(self.message_tabs)

        layout.addLayout(left, 1)
        layout.addLayout(right)

        self.saved_data = self.empty_data()
        self.load_saved()

    # ---- Database <-> screen ----

    def load_saved(self):
        """Fill the Drafts and Sent lists from the database."""
        for row in message_service.get_drafts(self.user["id"], self.kind):
            entry = self.entry_from_row(row, row["created_at"])
            self.drafts.append(entry)
            self.draft_list.addItem(self.label(entry))
        for row in message_service.get_sent(self.user["id"], self.kind):
            entry = self.entry_from_row(row, row["sent_at"])
            self.sent.append(entry)
            self.sent_list.addItem(self.label(entry))

    def entry_from_row(self, row, stamp):
        data = self.from_fields(row["recipient"], row["subject"] or "", row["body"])
        return {"id": row["id"], "data": data, "time": local_stamp(stamp)}

    def view_sent(self, *_args):
        row = self.sent_list.currentRow()
        if row < 0 or row >= len(self.sent):
            return
        entry = self.sent[row]
        recipient, subject, body = self.to_fields(entry["data"])
        MessageDialog(self.kind, recipient, subject, body,
                      entry["time"], self).exec()

    # ---- Subclass methods ----

    def build_form(self):
        raise NotImplementedError

    def empty_data(self):
        raise NotImplementedError

    def get_data(self):
        raise NotImplementedError

    def set_data(self, data):
        raise NotImplementedError

    def summary(self, data):
        raise NotImplementedError

    def recipient(self, data):
        raise NotImplementedError

    def preview(self, data):
        raise NotImplementedError

    def to_fields(self, data):
        """data -> (recipient, subject or None, body) for the database."""
        raise NotImplementedError

    def from_fields(self, recipient, subject, body):
        """The reverse of to_fields."""
        raise NotImplementedError

    # ---- Shared logic ----

    def label(self, entry):
        return f"{self.summary(entry['data'])} - {entry['time']}"

    def has_unsaved(self):
        if self.task is not None:        # a message is on its way: nothing to save
            return False
        data = self.get_data()
        return data != self.empty_data() and data != self.saved_data

    def ask_save(self):
        if not self.has_unsaved():
            return True

        answer = QMessageBox.question(
            self,
            "Unsaved draft",
            f"Do you want to save this {self.kind} as a draft?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )

        if answer == QMessageBox.Save:
            return self.save_draft()

        if answer == QMessageBox.Discard:
            self.reset_form()      # throw the text away
            return True

        return False

    def reset_form(self):
        self.set_data(self.empty_data())
        self.saved_data = self.empty_data()
        self.current = -1

        self.draft_list.blockSignals(True)
        self.draft_list.setCurrentRow(-1)
        self.draft_list.clearSelection()
        self.draft_list.blockSignals(False)

    def save_draft(self):
        data = self.get_data()

        if data == self.empty_data():
            QMessageBox.warning(
                self, "Draft", "Nothing to save yet."
            )
            return False

        recipient, subject, body = self.to_fields(data)
        user_id = self.user["id"]

        try:
            if self.current >= 0:
                draft_id = self.drafts[self.current]["id"]
                message_service.update_draft(user_id, draft_id, recipient, subject, body)
            else:
                draft_id = message_service.save_draft(
                    user_id, self.kind, recipient, subject, body)
        except sqlite3.Error:
            log.exception("Could not save the draft")
            QMessageBox.warning(self, "Draft", "The draft could not be saved.")
            return False

        entry = {"id": draft_id, "data": data, "time": now_stamp()}

        if self.current >= 0:
            self.drafts[self.current] = entry
            self.draft_list.item(self.current).setText(
                self.label(entry)
            )
        else:
            self.drafts.append(entry)
            self.draft_list.addItem(self.label(entry))

        self.reset_form()
        return True

    def load_draft(self, index):
        if index < 0 or index >= len(self.drafts) or index == self.current:
            return

        if not self.ask_save():
            self.draft_list.blockSignals(True)
            self.draft_list.setCurrentRow(self.current)
            self.draft_list.blockSignals(False)
            return

        self.current = index

        data = self.drafts[index]["data"]

        self.set_data(data)
        self.saved_data = data

        self.draft_list.blockSignals(True)
        self.draft_list.setCurrentRow(index)
        self.draft_list.blockSignals(False)

    def delete_draft(self):
        row = self.draft_list.currentRow()

        if row < 0:
            return

        answer = QMessageBox.question(
            self,
            "Delete draft",
            "Delete this draft?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        message_service.delete_draft(self.user["id"], self.drafts[row]["id"])

        self.draft_list.blockSignals(True)

        self.draft_list.takeItem(row)
        del self.drafts[row]

        if row == self.current:
            self.current = -1
            self.set_data(self.empty_data())
            self.saved_data = self.empty_data()

        elif row < self.current:
            self.current -= 1

        self.draft_list.setCurrentRow(self.current)
        self.draft_list.blockSignals(False)

    # ---- Send message ----

    # Subclass hooks for sending
    demo = True      # True = nothing really leaves the app (SMS for now)

    def problem_with(self, data):
        """Return a message if this data must not be sent, else None."""
        return None

    def deliver(self, data):
        """Hand the message to the provider, then call finish_send(data)."""
        self.finish_send(data)

    def is_busy(self):
        """True while a send runs (MainWindow asks before closing)."""
        return self.task is not None

    def shutdown(self):
        """Called by MainWindow on close: let a running send finish first,
        then handle its result so the message is recorded before the app exits."""
        if self.task is not None:
            self.task.wait(message_service.TIMEOUT * 1000 + 2000)
            QApplication.processEvents()

    def set_sending(self, busy):
        for widget in (self.form, self.save_button, self.delete_button,
                       self.draft_list, self.send_button):
            widget.setEnabled(not busy)
        self.send_button.setText("Sending…" if busy else f"Send {self.kind}")

    def send(self):
        if self.task is not None:                # one send at a time
            return
        data = self.get_data()

        if data == self.empty_data():
            QMessageBox.warning(
                self, self.kind, "Nothing to send yet."
            )
            return

        problem = self.problem_with(data)
        if problem:
            QMessageBox.warning(self, self.kind, problem)
            return

        self.deliver(data)

    def start_task(self, data, fn, *args, **kwargs):
        """Run the provider off the UI thread. Success records the message."""
        self.pending = data
        self.set_sending(True)
        self.task = Task(fn, *args, safe=(SendError,), **kwargs)
        self.task.succeeded.connect(self.on_sent)
        self.task.failed.connect(self.on_send_failed)
        self.task.finished.connect(self.cleanup_task)
        self.task.start()

    def on_sent(self, _result):
        self.finish_send(self.pending)

    def on_send_failed(self, message):
        # Nothing is recorded and the form keeps its text so the user can retry
        QMessageBox.warning(self, f"{self.kind} not sent", message)

    def cleanup_task(self):
        self.task = None
        self.pending = None
        self.set_sending(False)

    def finish_send(self, data):
        # Save message to Sent (and remove its draft, if it came from one)
        draft_id = self.drafts[self.current]["id"] if self.current >= 0 else None
        recipient, subject, body = self.to_fields(data)
        try:
            message_id = message_service.record_sent(
                self.user["id"], self.kind, recipient, subject, body, draft_id)
        except sqlite3.Error:
            # The message really went out, so still show it for this session
            log.exception("Could not store the sent message")
            message_id = None
            QMessageBox.warning(
                self, self.kind,
                f"The {self.kind} was sent but could not be saved to your history.")

        entry = {"id": message_id, "data": data, "time": now_stamp()}

        self.sent.insert(0, entry)               # newest first
        self.sent_list.insertItem(0, self.label(entry))

        # Remove the draft if an existing draft was sent
        if self.current >= 0:
            self.draft_list.blockSignals(True)

            self.draft_list.takeItem(self.current)
            del self.drafts[self.current]

            self.draft_list.blockSignals(False)

        SentDialog(self.kind, self.recipient(data), self.preview(data),
                   entry["time"], self, demo=self.demo).exec()

        self.reset_form()


class SmsTab(DraftTab):
    kind = "SMS"

    def build_form(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)

        self.number = QLineEdit()
        self.number.setPlaceholderText(
            "Mobile number (e.g. 09XXXXXXXXX)"
        )

        self.text = QTextEdit()
        self.text.setPlaceholderText("Type your message...")

        self.counter = QLabel("0 / 160")
        self.counter.setObjectName("muted")
        self.text.textChanged.connect(self.update_counter)

        for x in (self.number, self.text, self.counter):
            l.addWidget(x)

        return w

    def update_counter(self):
        n = len(self.text.toPlainText())
        note = "  (over 160: sent as 2 SMS)" if n > 160 else ""
        self.counter.setText(f"{n} / 160{note}")

    def empty_data(self):
        return {"number": "", "text": ""}

    def get_data(self):
        return {
            "number": self.number.text().strip(),
            "text": self.text.toPlainText().strip()
        }

    def set_data(self, d):
        self.number.setText(d["number"])
        self.text.setPlainText(d["text"])

    def summary(self, d):
        return f"{d['number'] or 'No number'}: {d['text'][:18]}"

    def recipient(self, d):
        return d["number"]

    def preview(self, d):
        return d["text"]

    def to_fields(self, d):
        return d["number"], None, d["text"]

    def from_fields(self, recipient, subject, body):
        return {"number": recipient, "text": body}


class EmailTab(DraftTab):
    kind = "Email"

    def build_form(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)

        self.to = QLineEdit()
        self.to.setPlaceholderText("To")

        self.subject = QLineEdit()
        self.subject.setPlaceholderText("Subject")

        self.body = QTextEdit()
        self.body.setPlaceholderText("Message body...")

        for x in (self.to, self.subject, self.body):
            l.addWidget(x)

        return w

    def empty_data(self):
        return {
            "to": "",
            "subject": "",
            "body": ""
        }

    def get_data(self):
        return {
            "to": self.to.text().strip(),
            "subject": self.subject.text().strip(),
            "body": self.body.toPlainText().strip()
        }

    def set_data(self, d):
        self.to.setText(d["to"])
        self.subject.setText(d["subject"])
        self.body.setPlainText(d["body"])

    def summary(self, d):
        return d["subject"] or "(no subject)"

    def recipient(self, d):
        return d["to"]

    def preview(self, d):
        return d["subject"] or "(no subject)"

    def to_fields(self, d):
        return d["to"], d["subject"], d["body"]

    def from_fields(self, recipient, subject, body):
        return {"to": recipient, "subject": subject, "body": body}

    # ---- Real sending through Brevo (message_service) ----

    demo = False

    def problem_with(self, d):
        if not d["to"]:
            return "Enter a recipient email address."
        if not is_valid_email(d["to"]):
            return "Please enter a valid email address."
        if not d["subject"]:
            return "Enter a subject."
        if not d["body"]:
            return "Write a message."
        return None

    def deliver(self, d):
        user = session.current()
        reply_to = (user["email"], user["full_name"]) if user else None
        self.start_task(d, message_service.send_email,
                        d["to"], d["subject"], d["body"], reply_to=reply_to)


class MessagePage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.sms = SmsTab()
        self.email = EmailTab()

        tabs = QTabWidget()

        tabs.addTab(self.sms, "SMS")
        tabs.addTab(self.email, "Email")

        layout.addWidget(tabs)

    def confirm_leave(self):
        return (
            self.sms.ask_save()
            and self.email.ask_save()
        )

    def is_busy(self):
        return self.sms.is_busy() or self.email.is_busy()

    def shutdown(self):
        self.sms.shutdown()
        self.email.shutdown()