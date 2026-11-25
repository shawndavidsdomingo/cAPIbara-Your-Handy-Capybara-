import csv
import json

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSpinBox,
    QComboBox, QCheckBox, QGroupBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QAbstractItemView)

from services import fake_service
from core import session
from services.fake_service import FakeDataError, FIELDS
from ui.widgets import make_label
from ui.workers import Task

PICKER_COLUMNS = 5      # checkboxes per row in the field picker

# what the user can export to: name -> (file extension, save-dialog filter)
EXPORT_FORMATS = {
    "Excel": (".xlsx", "Excel Files (*.xlsx)"),
    "CSV": (".csv", "CSV Files (*.csv)"),
    "JSON": (".json", "JSON Files (*.json)"),
}


class FakeDataPage(QWidget):
    """Pick the kinds of data, generate people from FakerAPI, keep them in SQLite."""

    wide = True      # tells MainWindow to widen the window on this page

    def __init__(self):
        super().__init__()
        self.user = session.current()
        self.generations = []    # {"id", "name", "time", "fields", "total", "rows"}
        self.sort_col = -1       # column being sorted (-1 = none)
        self.sort_state = 0      # 0 = default, 1 = A to Z, 2 = Z to A
        self.shown_rows = []     # rows on screen (this is what gets exported)
        self.task = None         # the background request, if any
        self.checks = {}         # field key -> its checkbox (filled by the picker)

        layout = QVBoxLayout(self)
        layout.addWidget(self.build_field_picker())
        layout.addLayout(self.build_top_bar())
        self.status = make_label("", "muted")
        layout.addWidget(self.status)

        body = QHBoxLayout()
        body.addLayout(self.build_history_panel())
        self.table = self.build_table()
        body.addWidget(self.table, 1)
        layout.addLayout(body, 1)

        self.load_history()

    # ---------- Building the screen ----------

    def build_field_picker(self):
        box = QGroupBox("What data should be generated?")
        outer = QVBoxLayout(box)

        grid = QGridLayout()
        for i, key in enumerate(FIELDS):
            check = QCheckBox(fake_service.label(key))
            check.setChecked(key in fake_service.DEFAULT_FIELDS)
            self.checks[key] = check
            grid.addWidget(check, i // PICKER_COLUMNS, i % PICKER_COLUMNS)
        outer.addLayout(grid)

        buttons = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.setObjectName("secondary")
        select_all.clicked.connect(lambda: self.set_all_checks(True))
        clear = QPushButton("Clear selection")
        clear.setObjectName("secondary")
        clear.clicked.connect(lambda: self.set_all_checks(False))
        buttons.addWidget(select_all)
        buttons.addWidget(clear)
        buttons.addStretch()
        outer.addLayout(buttons)
        return box

    def set_all_checks(self, checked):
        for check in self.checks.values():
            check.setChecked(checked)

    def build_top_bar(self):
        top = QHBoxLayout()
        top.addWidget(QLabel("Number of records:"))

        self.count = QSpinBox()
        self.count.setRange(fake_service.MIN_RECORDS, fake_service.MAX_RECORDS)
        self.count.setValue(fake_service.MIN_RECORDS)

        top.addWidget(self.count)
        top.addWidget(QLabel("Gender:"))
        self.gender = QComboBox()
        self.gender.addItems(list(fake_service.GENDERS))
        top.addWidget(self.gender)

        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self.generate)
        self.export_format = QComboBox()
        self.export_format.addItems(list(EXPORT_FORMATS))
        export = QPushButton("Export")
        export.clicked.connect(self.export_data)
        clear = QPushButton("Clear All")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear_all)

        for w in (self.generate_button, QLabel("Export as:"),
                  self.export_format, export, clear):
            top.addWidget(w)
        top.addStretch()
        return top

    def build_history_panel(self):
        left = QVBoxLayout()
        left.addWidget(QLabel("Generation History"))

        self.history = QListWidget()
        self.history.setObjectName("history")      # styled in theme.py
        self.history.setFixedWidth(270)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history.currentRowChanged.connect(self.show_generation)
        left.addWidget(self.history)
        return left

    def build_table(self):
        table = QTableWidget(0, 0)           # columns follow the batch's fields
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.sectionClicked.connect(self.sort_by_column)
        header.setMinimumSectionSize(60)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
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
        details = QLabel(f"{gen['time']}  ·  {gen['total']} records")
        details.setObjectName("muted")

        text = QVBoxLayout()
        text.setSpacing(0)
        for label in (name, details):
            # let clicks pass through so the row can be selected
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text.addWidget(label)

        trash = QPushButton("🗑")
        trash.setObjectName("trash")
        trash.setToolTip("Delete this generation")
        trash.setFixedSize(34, 30)
        trash.setCursor(Qt.CursorShape.PointingHandCursor)
        trash.clicked.connect(
            lambda checked=False, g=gen: self.delete_generation(g))

        lay.addLayout(text, 1)
        lay.addWidget(trash, 0, Qt.AlignmentFlag.AlignVCenter)

        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 52))
        self.history.addItem(item)
        self.history.setItemWidget(item, row)

    # ---------- Loading from the database ----------

    def load_history(self, select_id=None):
        """Reload the batches from SQLite and select one (default: the newest)."""
        self.generations = [dict(g, rows=None)
                            for g in fake_service.get_generations(self.user["id"])]
        self.history.blockSignals(True)
        self.history.clear()
        for gen in self.generations:
            self.add_history_item(gen)
        row = len(self.generations) - 1
        for i, gen in enumerate(self.generations):
            if gen["id"] == select_id:
                row = i
        self.history.setCurrentRow(row)      # -1 when empty
        self.history.blockSignals(False)
        self.show_generation()

    def current_generation(self):
        index = self.history.currentRow()
        if 0 <= index < len(self.generations):
            return self.generations[index]
        return None

    # ---------- Generate (FakerAPI on a background thread) ----------

    def selected_fields(self):
        return [key for key, check in self.checks.items() if check.isChecked()]

    def generate(self):
        if self.task is not None:
            return
        fields = self.selected_fields()
        if not fields:
            self.show_status(fake_service.MSG_NO_FIELDS, error=True)
            return
        gender = fake_service.GENDERS[self.gender.currentText()]

        self.generate_button.setEnabled(False)
        self.generate_button.setText("Generating...")
        self.show_status("Asking FakerAPI for data...")
        self.task = Task(fake_service.generate_and_save, self.user["id"],
                         self.count.value(), fields, gender,
                         safe=(FakeDataError,))
        self.task.succeeded.connect(self.on_generated)
        self.task.failed.connect(self.on_failed)
        self.task.finished.connect(self.on_finished)
        self.task.start()

    def on_generated(self, generation_id):
        self.show_status("Done. The records were saved.")
        self.load_history(select_id=generation_id)

    def on_failed(self, message):
        self.show_status(message, error=True)

    def on_finished(self):
        self.task = None
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate")

    def show_status(self, text, error=False):
        self.status.setObjectName("error" if error else "muted")
        self.status.style().unpolish(self.status)    # re-apply theme.py colours
        self.status.style().polish(self.status)
        self.status.setText(text)

    # MainWindow asks these before closing the app (same as the URL page)
    def is_busy(self):
        return self.task is not None

    def shutdown(self):
        task = self.task
        if task is not None:
            task.wait()          # the batch is saved inside the task itself

    # ---------- Delete / clear ----------

    def ask_yes_no(self, title, text):
        answer = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def delete_generation(self, gen):
        if not self.ask_yes_no(
                "Delete generation",
                f"Delete {gen['name']} ({gen['time']}) "
                f"and its {gen['total']} records?"):
            return
        selected = self.current_generation()
        index = self.generations.index(gen)
        fake_service.delete_generation(self.user["id"], gen["id"])

        if selected is not gen:
            keep = selected["id"]                 # keep the same batch selected
        else:                                     # pick its neighbour
            rest = [g for g in self.generations if g is not gen]
            keep = rest[min(index, len(rest) - 1)]["id"] if rest else None
        self.load_history(select_id=keep)

    def clear_all(self):
        if not self.generations:
            return
        if not self.ask_yes_no(
                "Clear All",
                "Delete all generations and their records?\n"
                "This cannot be undone."):
            return
        fake_service.clear_generations(self.user["id"])
        self.load_history()

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
        gen = self.current_generation()
        fields, rows = [], []
        if gen is not None:
            if gen["rows"] is None:          # records load when first shown
                gen["rows"] = fake_service.get_records(self.user["id"], gen["id"])
            fields = gen["fields"]
            rows = list(gen["rows"])         # copy: keep original order

        if self.sort_state != 0 and self.sort_col < len(fields):
            key = fields[self.sort_col]
            rows.sort(key=lambda r: r.get(key, "").casefold(),
                      reverse=(self.sort_state == 2))
        self.shown_rows = rows

        labels = [fake_service.label(key) for key in fields]
        if self.sort_state == 1:             # add ▲ / ▼ to the sorted column
            labels[self.sort_col] += "  ▲"
        elif self.sort_state == 2:
            labels[self.sort_col] += "  ▼"

        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(fields):
                self.table.setItem(r, c, QTableWidgetItem(row.get(key, "")))

    # ---------- Export (Excel, CSV or JSON) ----------

    def export_data(self):
        gen = self.current_generation()
        if gen is None:
            QMessageBox.warning(self, "Export", "Generate some data first.")
            return

        kind = self.export_format.currentText()
        extension, file_filter = EXPORT_FORMATS[kind]
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export to {kind}", f"{gen['name']}{extension}", file_filter)
        if not path:
            return
        if not path.lower().endswith(extension):
            path += extension

        labels = [fake_service.label(key) for key in gen["fields"]]
        # same order as the table; each row is a list of values in column order
        table_rows = [[row.get(key, "") for key in gen["fields"]]
                      for row in self.shown_rows]
        try:
            if kind == "Excel":
                if not self.write_excel(path, gen["name"], labels, table_rows):
                    return
            elif kind == "CSV":
                self.write_csv(path, labels, table_rows)
            else:
                self.write_json(path, labels, table_rows)
        except OSError as error:              # e.g. file is open in Excel
            QMessageBox.warning(self, "Export", f"Could not save the file:\n{error}")
            return
        QMessageBox.information(self, "Export", f"Saved {gen['name']} to:\n{path}")

    def write_excel(self, path, title, labels, table_rows):
        try:                                  # imported here so a missing
            from openpyxl import Workbook     # package cannot stop the app
        except ModuleNotFoundError:
            QMessageBox.warning(
                self, "Export",
                "Excel export needs openpyxl.\nInstall it with: pip install openpyxl")
            return False
        wb = Workbook()
        ws = wb.active
        ws.title = title
        ws.append(labels)
        for row in table_rows:
            ws.append(row)
        wb.save(path)
        return True

    def write_csv(self, path, labels, table_rows):
        # utf-8-sig so Excel shows accents correctly; newline="" is what csv expects
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(labels)
            writer.writerows(table_rows)

    def write_json(self, path, labels, table_rows):
        records = [dict(zip(labels, row)) for row in table_rows]
        with open(path, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)