"""Contacts: the people a user can text or email (storage and checks).

The GUI calls these functions and never touches SQL. Every query is scoped to
the user's id and uses ? placeholders. Functions raise ValueError with a
message that is safe to show to the user.

A contact has a name plus a mobile number, an email address, or both.
Mobile numbers are saved the way the SMS tab expects them (09XXXXXXXXX), so
"+63 917 123 4567" is stored as 09171234567.
"""
import re

from core.db import connection
from services.auth_service import is_valid_email
from services.message_service import MSG_BAD_NUMBER, is_valid_ph_mobile

MAX_NAME = 60
COLUMNS = "id, name, mobile, email"


# ---------- Cleaning and checking ----------

def clean_mobile(number):
    """'+63 917-123-4567' or '639171234567' -> '09171234567'.

    Spaces, dashes, dots and brackets are dropped. Anything that still is not a
    Philippine mobile number is returned as it is, for check() to refuse."""
    digits = re.sub(r"[\s\-().]", "", number or "")
    if digits.startswith("+63"):
        digits = "0" + digits[3:]
    elif digits.startswith("63") and len(digits) == 12:
        digits = "0" + digits[2:]
    return digits


def check(name, mobile, email):
    """Return the cleaned (name, mobile, email) or raise ValueError."""
    name = " ".join((name or "").split())
    mobile = clean_mobile(mobile)
    email = (email or "").strip()
    if not name:
        raise ValueError("Please enter a name.")
    if len(name) > MAX_NAME:
        raise ValueError(f"The name is too long (up to {MAX_NAME} characters).")
    if not mobile and not email:
        raise ValueError("Enter a mobile number, an email address, or both.")
    if mobile and not is_valid_ph_mobile(mobile):
        raise ValueError(MSG_BAD_NUMBER)
    if email and not is_valid_email(email):
        raise ValueError("Please enter a valid email address.")
    return name, mobile, email


def _check_not_duplicate(conn, user_id, mobile, email, skip_id=0):
    """One contact per number and per address (for this user)."""
    for column, value, what in (("mobile", mobile, "mobile number"),
                                ("email", email, "email address")):
        if not value:
            continue
        row = conn.execute(
            f"SELECT name FROM contacts WHERE user_id = ? AND {column} = ? "
            "COLLATE NOCASE AND id != ?", (user_id, value, skip_id)).fetchone()
        if row:
            raise ValueError(f"{row['name']} already has that {what}.")


# ---------- Storage (every query is scoped to the user) ----------

def add_contact(user_id, name, mobile="", email=""):
    """Save a new contact and return its id."""
    name, mobile, email = check(name, mobile, email)
    with connection() as conn:
        _check_not_duplicate(conn, user_id, mobile, email)
        cursor = conn.execute(
            "INSERT INTO contacts (user_id, name, mobile, email) VALUES (?, ?, ?, ?)",
            (user_id, name, mobile, email))
        return cursor.lastrowid


def update_contact(user_id, contact_id, name, mobile="", email=""):
    """Change a contact. Raises ValueError if it is invalid or no longer exists."""
    name, mobile, email = check(name, mobile, email)
    with connection() as conn:
        _check_not_duplicate(conn, user_id, mobile, email, skip_id=contact_id)
        cursor = conn.execute(
            "UPDATE contacts SET name = ?, mobile = ?, email = ? "
            "WHERE id = ? AND user_id = ?", (name, mobile, email, contact_id, user_id))
        if cursor.rowcount == 0:
            raise ValueError("That contact no longer exists.")


def delete_contact(user_id, contact_id):
    """True if a contact was deleted."""
    with connection() as conn:
        cursor = conn.execute("DELETE FROM contacts WHERE id = ? AND user_id = ?",
                              (contact_id, user_id))
        return cursor.rowcount > 0


def get_contacts(user_id):
    """All of the user's contacts, A to Z by name."""
    sql = (f"SELECT {COLUMNS} FROM contacts WHERE user_id = ? "
           "ORDER BY name COLLATE NOCASE, id")
    with connection() as conn:
        return [dict(row) for row in conn.execute(sql, (user_id,)).fetchall()]


def filter_contacts(contacts, query="", need=None):
    """Search a list from get_contacts() without touching the database.

    query  text to find in the name, mobile or email (any case)
    need   "mobile" or "email": keep only contacts that have one (for the pickers)
    """
    query = query.strip().casefold()
    return [c for c in contacts
            if (not need or c[need])
            and (not query
                 or query in c["name"].casefold()
                 or query in c["mobile"]
                 or query in c["email"].casefold())]
