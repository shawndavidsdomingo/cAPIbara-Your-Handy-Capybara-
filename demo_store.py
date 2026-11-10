"""Temporary in-memory 'database' for the GUI-only sprint.

Everything here is replaced by SQLite + hashed passwords in the next sprint.
Data is lost when the app closes.
"""
import re

USERS = {
    "admin": {
        "full_name": "admin",
        "email": "admin@example.com",
        "password": "admin123",     # plain text ONLY for the demo
    }
}


def check_login(username, password):
    user = USERS.get(username)
    return user is not None and user["password"] == password


def username_taken(username):
    return username in USERS


def add_user(username, full_name, email, password):
    USERS[username] = {"full_name": full_name, "email": email,
                       "password": password}


def get_user(username):
    return USERS[username]


def is_valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def is_valid_username(username):
    """3-20 characters: letters, numbers and underscores only."""
    return re.fullmatch(r"[A-Za-z0-9_]{3,20}", username) is not None


def mask_email(email):
    """juan.cruz@example.com -> ju***@example.com"""
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"