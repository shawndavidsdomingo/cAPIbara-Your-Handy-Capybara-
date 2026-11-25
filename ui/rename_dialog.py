"""Pop-up for renaming a Fake Data generation (put this file in ui/).

Reuses the helpers in dialogs.py so it looks like the other dialogs. An empty
name puts the default ("Gen 3") back. The service checks the name and saves it.
"""
from PySide6.QtWidgets import QDialog

from services import fake_service
from ui.dialogs import error_line, make_dialog_layout, quiet
from ui.widgets import make_button, make_input, make_label


class RenameGenerationDialog(QDialog):
    """Accepted when the new name was saved."""

    def __init__(self, user_id, gen, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Generation")
        self.user_id = user_id
        self.gen = gen
        layout = make_dialog_layout(self, "Rename generation")

        default = fake_service.default_name(gen["number"])
        info = quiet(f"Give it a name that tells you what it is for. "
                     f"Leave it empty to use {default}.")

        self.name = make_input(default)
        self.name.setMaxLength(fake_service.MAX_NAME)
        if gen["custom"]:
            self.name.setText(gen["name"])
            self.name.selectAll()
        self.name.returnPressed.connect(self.submit)
        self.error = error_line()

        layout.addWidget(info)
        layout.addSpacing(6)
        layout.addWidget(make_label("Name", "fieldLabel"))
        layout.addWidget(self.name)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Save name", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.name.setFocus()

    def submit(self):
        try:
            fake_service.rename_generation(self.user_id, self.gen["id"],
                                           self.name.text())
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.accept()
