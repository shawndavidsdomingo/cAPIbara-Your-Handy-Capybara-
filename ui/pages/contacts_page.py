from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout,
                               QHeaderView, QMessageBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core import session
from services import contact_service
from ui.dialogs import ContactDialog
from ui.theme import COLORS
from ui.widgets import make_button, make_card, make_input, make_label

COLUMNS = (("name", "Name"), ("mobile", "Mobile"), ("email", "Email"))


class ContactsPage(QWidget):
    """The user's address book. Add, edit and delete people here; the SMS and
    Email tabs pick from this list. Saved through contact_service."""

    def __init__(self):
        super().__init__()
        self.user = session.current()           # the logged-in user's dict
        self.contacts = []                      # all of the user's contacts
        self.shown = []                         # what the table shows now

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addWidget(make_label("Contacts", "title"))
        outer.addWidget(make_label("The people you text and email.", "muted"))
        outer.addSpacing(10)

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = make_input("Search by name, mobile or email")
        self.search.textChanged.connect(self.show_rows)
        top.addWidget(self.search, 1)
        top.addWidget(make_button("Add contact", self.add_contact))
        layout.addLayout(top)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([title for _key, title in COLUMNS])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)   # headers line up with the cells
        self.table.verticalHeader().setDefaultSectionSize(40)
        # the same side padding on headers (12px) and cells (9px + Qt's own 3px margin)
        self.table.setStyleSheet(
            "QTableWidget::item { padding: 0px 9px; }"
            "QHeaderView::section { padding: 8px 12px; }")
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setToolTip("Double-click a contact to edit it")
        self.table.itemSelectionChanged.connect(self.sync_buttons)
        self.table.cellDoubleClicked.connect(lambda *_args: self.edit_contact())
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.count = make_label("", "muted")
        self.edit_button = make_button("Edit", self.edit_contact, secondary=True)
        self.delete_button = make_button("Delete", self.delete_contact, secondary=True)
        bottom.addWidget(self.count, 1)
        bottom.addWidget(self.edit_button)
        bottom.addWidget(self.delete_button)
        layout.addLayout(bottom)

        outer.addWidget(card, 1)
        self.refresh()

    # ---------- Loading ----------

    def refresh(self):
        """Called by MainWindow every time this page is opened."""
        self.contacts = contact_service.get_contacts(self.user["id"])
        self.show_rows()

    def show_rows(self):
        keep = self.selected_id()
        self.shown = contact_service.filter_contacts(self.contacts, self.search.text())

        self.table.setRowCount(len(self.shown))
        for row, contact in enumerate(self.shown):
            for col, (key, _title) in enumerate(COLUMNS):
                item = QTableWidgetItem(contact[key] or "\u2014")   # a dash if empty
                if not contact[key]:
                    item.setForeground(QColor(COLORS["muted"]))
                self.table.setItem(row, col, item)
            if contact["id"] == keep:
                self.table.selectRow(row)

        if not self.contacts:
            self.count.setText("No contacts yet. Click Add contact to create one.")
        elif not self.shown:
            self.count.setText("No contacts match your search.")
        else:
            total = len(self.contacts)
            self.count.setText(f"{total} contact{'s' if total != 1 else ''}"
                               if len(self.shown) == total
                               else f"{len(self.shown)} of {total} contacts")
        self.sync_buttons()

    def selected_contact(self):
        row = self.table.currentRow()
        if self.table.selectedItems() and 0 <= row < len(self.shown):
            return self.shown[row]
        return None

    def selected_id(self):
        contact = self.selected_contact()
        return contact["id"] if contact else None

    def sync_buttons(self):
        chosen = self.selected_contact() is not None
        self.edit_button.setEnabled(chosen)
        self.delete_button.setEnabled(chosen)

    # ---------- Add, edit, delete ----------

    def add_contact(self):
        dialog = ContactDialog(self.user["id"], parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.search.clear()                 # so the new contact is visible
            self.refresh()

    def edit_contact(self):
        contact = self.selected_contact()
        if contact is None:
            return
        dialog = ContactDialog(self.user["id"], contact, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()

    def delete_contact(self):
        contact = self.selected_contact()
        if contact is None:
            return
        answer = QMessageBox.question(
            self, "Delete contact", f"Delete {contact['name']} from your contacts?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        contact_service.delete_contact(self.user["id"], contact["id"])
        self.refresh()