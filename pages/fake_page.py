import random
from datetime import datetime

import stats

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QAbstractItemView)

COLUMNS = ["Full Name", "Address", "Birthdate", "Mobile", "Email",
           "Gender", "Civil Status", "Occupation", "City", "Zip Code"]

FIRST = ["Juan", "Maria", "Jose", "Ana", "Mark", "Grace", "Paolo", "Liza"]
LAST = ["Santos", "Reyes", "Cruz", "Garcia", "Bautista", "Mendoza"]
JOBS = ["Student", "Teacher", "Engineer", "Nurse", "Clerk", "Designer"]
CITIES = ["Quezon City", "Manila", "Cebu City", "Davao City", "Baguio"]


def make_record():
    """One fake person = one list of 10 values, in COLUMNS order."""
    first, last = random.choice(FIRST), random.choice(LAST)
    birthdate = (f"{random.randint(1990, 2005)}-"
                 f"{random.randint(1, 12):02d}-{random.randint(1, 28):02d}")
    return [
        f"{first} {last}",
        f"{random.randint(1, 999)} Sample St.",
        birthdate,
        f"09{random.randint(100000000, 999999999)}",
        f"{first.lower()}.{last.lower()}@example.com",
        random.choice(["Male", "Female"]),
        random.choice(["Single", "Married"]),
        random.choice(JOBS),
        random.choice(CITIES),
        str(random.randint(1000, 9999)),
    ]


class FakeDataPage(QWidget):
    wide = True      # tells MainWindow to widen the window on this page

    def __init__(self):
        super().__init__()
        self.generations = []    # every batch: {"name", "time", "rows"}
        self.gen_counter = 0     # only goes up, so "Gen 2" is never reused
        self.sort_col = -1       # column being sorted (-1 = none)
        self.sort_state = 0      # 0 = default, 1 = A to Z, 2 = Z to A
        self.shown_rows = []     # rows on screen (this is what gets exported)

        layout = QVBoxLayout(self)
        layout.addLayout(self.build_top_bar())

        body = QHBoxLayout()
        body.addLayout(self.build_history_panel())
        self.table = self.build_table()
        body.addWidget(self.table, 1)
        layout.addLayout(body)

    # ---------- Building the screen ----------

    def build_top_bar(self):
        top = QHBoxLayout()
        top.addWidget(QLabel("Number of records:"))

        self.count = QSpinBox()
        self.count.setRange(10, 1000)       # project needs at least 10
        self.count.setValue(10)

        generate = QPushButton("Generate")
        generate.clicked.connect(self.generate)
        export = QPushButton("Export to Excel")
        export.clicked.connect(self.export_excel)
        clear = QPushButton("Clear All")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear_all)

        for w in (self.count, generate, export, clear):
            top.addWidget(w)
        top.addStretch()
        return top

    def build_history_panel(self):
        left = QVBoxLayout()
        left.addWidget(QLabel("Generation History"))

        self.history = QListWidget()
        self.history.setObjectName("history")      # styled in theme.py
        self.history.setFixedWidth(270)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.history.currentRowChanged.connect(self.show_generation)
        left.addWidget(self.history)
        return left

    def build_table(self):
        table = QTableWidget(0, len(COLUMNS))
        table.setHorizontalHeaderLabels(COLUMNS)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.sectionClicked.connect(self.sort_by_column)
        header.setMinimumSectionSize(60)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Fixed)    # Address: fixed
        table.setColumnWidth(1, 130)
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Email: takes the rest
        return table

    def add_history_item(self, gen):
        """One history row = name + time/count + trash button."""
        row = QWidget()
        row.setObjectName("historyRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 6, 6)
        lay.setSpacing(6)

        name = QLabel(gen["name"])
        name.setObjectName("bold")
        details = QLabel(f"{gen['time']}  ·  {len(gen['rows'])} records")
        details.setObjectName("muted")

        text = QVBoxLayout()
        text.setSpacing(0)
        for label in (name, details):
            # let clicks pass through so the row can be selected
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
            text.addWidget(label)

        trash = QPushButton("🗑")
        trash.setObjectName("trash")
        trash.setToolTip("Delete this generation")
        trash.setFixedSize(34, 30)
        trash.setCursor(Qt.PointingHandCursor)
        trash.clicked.connect(
            lambda checked=False, g=gen: self.delete_generation(g))

        lay.addLayout(text, 1)
        lay.addWidget(trash, 0, Qt.AlignVCenter)

        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 52))
        self.history.addItem(item)
        self.history.setItemWidget(item, row)

    # ---------- Generate / delete / clear ----------

    def generate(self):
        self.gen_counter += 1
        gen = {
            "name": f"Gen {self.gen_counter}",
            "time": datetime.now().strftime("%H:%M:%S"),
            "rows": [make_record() for _ in range(self.count.value())],
        }
        self.generations.append(gen)
        stats.record_generation(gen["name"])
        self.add_history_item(gen)
        self.history.setCurrentRow(len(self.generations) - 1)   # shows it

    def ask_yes_no(self, title, text):
        answer = QMessageBox.question(
            self, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def delete_generation(self, gen):
        if not self.ask_yes_no(
                "Delete generation",
                f"Delete {gen['name']} ({gen['time']}) "
                f"and its {len(gen['rows'])} records?"):
            return

        index = self.generations.index(gen)
        selected = self.history.currentRow()

        self.generations.pop(index)
        self.history.blockSignals(True)      # we refresh the table ourselves
        self.history.takeItem(index)
        self.history.blockSignals(False)

        # Keep the same batch selected, or pick its neighbour if it was deleted
        if index < selected:
            selected -= 1
        selected = min(selected, len(self.generations) - 1)   # -1 when empty
        self.history.setCurrentRow(selected)
        self.show_generation()

    def clear_all(self):
        if not self.generations:
            return
        if not self.ask_yes_no(
                "Clear All",
                "Delete all generations and their records?\n"
                "This cannot be undone."):
            return
        self.generations.clear()
        self.history.clear()
        self.show_generation()               # empties the table

    # ---------- Showing and sorting ----------

    def show_generation(self, _index=None):
        self.sort_col = -1                   # a new batch starts unsorted
        self.sort_state = 0
        self.refresh_table()

    def sort_by_column(self, col):
        """Click a header: Default -> A to Z -> Z to A -> Default."""
        if col != self.sort_col:
            self.sort_col = col
            self.sort_state = 1
        else:
            self.sort_state = (self.sort_state + 1) % 3
            if self.sort_state == 0:
                self.sort_col = -1
        self.refresh_table()

    def refresh_table(self):
        index = self.history.currentRow()
        rows = []
        if 0 <= index < len(self.generations):
            rows = list(self.generations[index]["rows"])   # copy: keep original order

        if self.sort_state != 0:
            rows.sort(key=lambda r: r[self.sort_col].casefold(),
                      reverse=(self.sort_state == 2))
        self.shown_rows = rows

        labels = list(COLUMNS)               # add ▲ / ▼ to the sorted column
        if self.sort_state == 1:
            labels[self.sort_col] += "  ▲"
        elif self.sort_state == 2:
            labels[self.sort_col] += "  ▼"
        self.table.setHorizontalHeaderLabels(labels)

        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(value))

    # ---------- Export ----------

    def export_excel(self):
        index = self.history.currentRow()
        if index < 0:
            QMessageBox.warning(self, "Export", "Generate some data first.")
            return

        try:                                  # imported here so a missing
            from openpyxl import Workbook     # package cannot stop the app
        except ModuleNotFoundError:
            QMessageBox.warning(
                self, "Export",
                "Excel export needs openpyxl.\nInstall it with: pip install openpyxl")
            return

        gen = self.generations[index]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", f"{gen['name']}.xlsx",
            "Excel Files (*.xlsx)")
        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = gen["name"]
        ws.append(COLUMNS)
        for row in self.shown_rows:           # same order as the table
            ws.append(row)

        try:
            wb.save(path)
        except OSError as error:              # e.g. file is open in Excel
            QMessageBox.warning(self, "Export", f"Could not save the file:\n{error}")
            return
        QMessageBox.information(self, "Export", f"Saved {gen['name']} to:\n{path}")