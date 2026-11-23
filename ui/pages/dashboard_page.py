from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from core import session
from services import stats
from ui.widgets import make_label


class StatCard(QWidget):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)   # lets the stylesheet paint it
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        self.value = make_label("0", "statNumber")
        layout.addWidget(make_label(title, "muted"))
        layout.addWidget(self.value)

    def set_value(self, text):
        self.value.setText(str(text))


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.user = session.current()

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignTop)
        outer.setSpacing(16)

        self.welcome = make_label("", "title")
        outer.addWidget(self.welcome)
        outer.addWidget(make_label("Here is your activity so far.", "muted"))

        self.emails = StatCard("Emails sent")
        self.sms = StatCard("Texts sent")
        self.links = StatCard("Links shortened")
        row = QHBoxLayout()
        row.setSpacing(16)
        for card in (self.emails, self.sms, self.links):
            row.addWidget(card)
        outer.addLayout(row)

        self.gens = StatCard("Fake data generations created")
        self.gen_ids = make_label("", "bold")
        self.gen_ids.setWordWrap(True)
        self.gens.layout().addWidget(self.gen_ids)
        outer.addWidget(self.gens)

    def refresh(self):
        """Called by MainWindow every time this page is opened."""
        self.welcome.setText(f"Welcome back, {self.user['full_name']}!")
        self.emails.set_value(stats.count_emails(self.user["id"]))
        self.sms.set_value(stats.count_sms(self.user["id"]))
        self.links.set_value(stats.count_links(self.user["id"]))
        self.gens.set_value(stats.count_generations(self.user["id"]))
        self.gen_ids.setText(", ".join(stats.generation_names(self.user["id"])) or "None yet")