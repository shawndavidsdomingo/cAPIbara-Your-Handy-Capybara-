"""Forgot username or password (put this file in ui/).

It works like Change password: the person proves they own the account's email
with a one-time code, then sets a new password. Steps:

  1. FindAccountDialog   - type the email OR the username of the account
  2. verify_otp          - a code is sent to the account's email
  3. ResetPasswordDialog - shows the username and asks for a new password

Call forgot_password(parent). It returns the username when the password was
changed (so the Login form can fill it in), or None if the person gave up.

The dialogs reuse the helpers in dialogs.py, so they look like the others.
"""
from PySide6.QtWidgets import QDialog, QMessageBox

from services import auth_service
from ui.dialogs import error_line, make_dialog_layout, quiet, verify_otp
from ui.widgets import make_button, make_input, make_label


class FindAccountDialog(QDialog):
    """Step 1: which account? Accepted when one was found (see .user)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forgot Username or Password")
        self.user = None
        layout = make_dialog_layout(self, "Find your account")

        info = quiet("Enter your email or username. We will send a code to the "
                     "email on the account.")

        self.login = make_input("Email or username")
        self.login.returnPressed.connect(self.submit)
        self.error = error_line()

        layout.addWidget(info)
        layout.addSpacing(6)
        layout.addWidget(make_label("Email or username", "fieldLabel"))
        layout.addWidget(self.login)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Send code", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.login.setFocus()

    def submit(self):
        text = self.login.text().strip()
        if not text:
            self.error.setText("Enter your email or username.")
            return
        user = auth_service.find_user_by_login(text)
        if user is None:
            self.error.setText("No account found with that email or username.")
            return
        self.user = user
        self.accept()


class ResetPasswordDialog(QDialog):
    """Step 3: show the username and set a new password. Accepted when saved.

    Unlike NewPasswordDialog it does not ask for the current password (the
    person forgot it): the one-time code already proved who they are."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set New Password")
        self.user = user
        layout = make_dialog_layout(self, "Set new password")

        who = make_label(f"Your username is: {user['username']}", "bold")
        who.setWordWrap(True)

        self.new = make_input("New password (8+ characters)", password=True)
        self.confirm = make_input("Confirm new password", password=True)
        self.new.returnPressed.connect(self.confirm.setFocus)
        self.confirm.returnPressed.connect(self.submit)
        self.error = error_line()

        layout.addWidget(who)
        layout.addSpacing(6)
        for text, field in (("New password", self.new),
                            ("Confirm new password", self.confirm)):
            layout.addWidget(make_label(text, "fieldLabel"))
            layout.addWidget(field)
            layout.addSpacing(4)
        layout.addWidget(self.error)
        layout.addWidget(make_button("Save password", self.submit))
        layout.addWidget(make_button("Cancel", self.reject, secondary=True))
        self.new.setFocus()

    def submit(self):
        new, confirm = self.new.text(), self.confirm.text()
        if len(new) < 8:
            self.error.setText("Password must be at least 8 characters.")
        elif new != confirm:
            self.error.setText("Passwords do not match.")
        else:
            try:
                auth_service.reset_password(self.user["id"], new)
            except ValueError as error:
                self.error.setText(str(error))
            else:
                self.accept()


def forgot_password(parent):
    """Run the whole flow. Returns the username on success, otherwise None."""
    finder = FindAccountDialog(parent)
    if finder.exec() != QDialog.Accepted:
        return None
    user = finder.user

    if not verify_otp(parent, user["email"], "Confirm it's you"):
        return None                       # cancelled before the code was verified

    if ResetPasswordDialog(user, parent).exec() != QDialog.Accepted:
        return None

    QMessageBox.information(parent, "Password updated",
                            "Your password was changed. You can now log in.")
    return user["username"]
