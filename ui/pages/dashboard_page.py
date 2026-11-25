from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from core import session
from services import stats
from ui.charts import BarChart, ColorDot, DonutChart
from ui.theme import CHART_COLORS
from ui.widgets import make_card, make_label

# (key in the stats, name shown to the user), in the order they are stacked
KINDS = (("emails", "Emails"), ("sms", "Texts"), ("links", "Links"), ("gens", "Data"))
SERIES = [(key, name, CHART_COLORS[key]) for key, name in KINDS]
DAYS = 7


class StatCard(QWidget):
    """A small card: a quiet title and one big number."""

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(2)
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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.welcome = make_label("", "title")
        outer.addWidget(self.welcome)
        outer.addWidget(make_label("Here is your activity so far.", "muted"))
        outer.addSpacing(14)

        self.emails = StatCard("Emails sent")
        self.sms = StatCard("Texts sent")
        self.links = StatCard("Links shortened")
        self.gens = StatCard("Data generations")
        row = QHBoxLayout()
        row.setSpacing(16)
        for card in (self.emails, self.sms, self.links, self.gens):
            row.addWidget(card, 1)
        outer.addLayout(row)
        outer.addSpacing(14)

        # Charts: the last 7 days (bars) and the totals by kind (donut)
        charts = QHBoxLayout()
        charts.setSpacing(16)
        charts.addWidget(self.build_activity_card(), 3)
        charts.addWidget(self.build_breakdown_card(), 2)
        outer.addLayout(charts, 1)
        outer.addSpacing(14)

        # The names of the fake data batches ("Gen 1, Gen 2, ...")
        history = make_card()
        history_layout = QVBoxLayout(history)
        history_layout.setContentsMargins(20, 18, 20, 18)
        history_layout.setSpacing(8)
        history_layout.addWidget(make_label("Fake data generations", "bold"))
        self.gen_ids = make_label("", "muted")
        self.gen_ids.setWordWrap(True)
        history_layout.addWidget(self.gen_ids)
        outer.addWidget(history)

    # ---------- Building the charts ----------

    def build_activity_card(self):
        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(make_label(f"Last {DAYS} days", "bold"))
        header.addStretch()
        for _key, name, color in SERIES:                # the legend
            header.addSpacing(8)
            header.addWidget(ColorDot(color))
            header.addWidget(make_label(name, "muted"))
        layout.addLayout(header)

        self.bars = BarChart(SERIES)
        layout.addWidget(self.bars, 1)
        return card

    def build_breakdown_card(self):
        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(8)
        layout.addWidget(make_label("All time", "bold"))

        body = QHBoxLayout()
        body.setSpacing(16)
        self.donut = DonutChart()
        body.addWidget(self.donut, 1)

        legend = QVBoxLayout()
        legend.setSpacing(8)
        legend.addStretch()
        self.legend_values = {}
        for key, name, color in SERIES:
            line = QHBoxLayout()
            line.setSpacing(8)
            line.addWidget(ColorDot(color))
            line.addWidget(make_label(name, "muted"))
            line.addSpacing(6)
            value = make_label("0", "bold")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.legend_values[key] = value
            line.addWidget(value)
            legend.addLayout(line)
        legend.addStretch()
        body.addLayout(legend)
        layout.addLayout(body, 1)
        return card

    # ---------- Loading the numbers ----------

    def refresh(self):
        """Called by MainWindow every time this page is opened."""
        user_id = self.user["id"]
        counts = {"emails": stats.count_emails(user_id),
                  "sms": stats.count_sms(user_id),
                  "links": stats.count_links(user_id),
                  "gens": stats.count_generations(user_id)}

        self.welcome.setText(f"Welcome back, {self.user['full_name']}!")
        self.emails.set_value(counts["emails"])
        self.sms.set_value(counts["sms"])
        self.links.set_value(counts["links"])
        self.gens.set_value(counts["gens"])
        self.gen_ids.setText(", ".join(stats.generation_names(user_id))
                             or "None yet. Create one on the Fake Data page.")

        days = []
        for day in stats.activity_by_day(user_id, DAYS):
            when = datetime.strptime(day["date"], "%Y-%m-%d")
            days.append({"label": when.strftime("%a"),
                         "title": when.strftime("%a, %b %d"),
                         "values": {key: day[key] for key, _name in KINDS}})
        self.bars.set_data(days)

        self.donut.set_data([(name, counts[key], CHART_COLORS[key]) for key, name in KINDS])
        for key, label in self.legend_values.items():
            label.setText(str(counts[key]))