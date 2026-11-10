from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QMessageBox
)

import stats
from dialogs import SentDialog


class DraftTab(QWidget):
    """Shared draft and sent message logic."""

    kind = ""

    def __init__(self):
        super().__init__()

        self.drafts = []
        self.sent = []
        self.current = -1

        layout = QHBoxLayout(self)

        # Left: Message form
        left = QVBoxLayout()
        left.addWidget(self.build_form())

        buttons = QHBoxLayout()

        save = QPushButton("Save Draft")
        save.clicked.connect(self.save_draft)

        send = QPushButton(f"Send {self.kind}")
        send.clicked.connect(self.send)

        buttons.addWidget(save)
        buttons.addWidget(send)

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

        delete = QPushButton("Delete Draft")
        delete.setObjectName("secondary")
        delete.clicked.connect(self.delete_draft)

        draft_layout.addWidget(self.draft_list)
        draft_layout.addWidget(delete)

        # Sent tab
        sent_page = QWidget()
        sent_layout = QVBoxLayout(sent_page)

        self.sent_list = QListWidget()

        sent_layout.addWidget(self.sent_list)

        self.message_tabs.addTab(draft_page, "Drafts")
        self.message_tabs.addTab(sent_page, "Sent")

        right.addWidget(self.message_tabs)

        layout.addLayout(left, 1)
        layout.addLayout(right)

        self.saved_data = self.empty_data()

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

    # ---- Shared logic ----

    def label(self, entry):
        return f"{self.summary(entry['data'])} - {entry['time']}"

    def has_unsaved(self):
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

        entry = {
            "data": data,
            "time": datetime.now().strftime("%H:%M:%S")
        }

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

    def send(self):
        data = self.get_data()

        if data == self.empty_data():
            QMessageBox.warning(
                self, self.kind, "Nothing to send yet."
            )
            return

        # Save message to Sent
        entry = {
            "data": data,
            "time": datetime.now().strftime("%H:%M:%S")
        }

        self.sent.append(entry)
        stats.record_sent(self.kind)
        self.sent_list.addItem(self.label(entry))

        # Remove the draft if an existing draft was sent
        if self.current >= 0:
            self.draft_list.blockSignals(True)

            self.draft_list.takeItem(self.current)
            del self.drafts[self.current]

            self.draft_list.blockSignals(False)

        SentDialog(self.kind, self.recipient(data), self.preview(data),
                   entry["time"], self).exec()

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