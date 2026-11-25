"""Register, login and profile updates.

The GUI calls these functions and never touches SQL.
Passwords are stored
only as a random salt + PBKDF2-SHA256 hash.
Every statement uses ? placeholders.
Functions raise ValueError with a message that is safe to show to the user.
"""
import hashlib
import hmac
import os
import re
import sqlite3

from core.db import connection

ITERATIONS = 200_000
MIN_PASSWORD = 8
PUBLIC_COLUMNS = "id, username, full_name, email"   # never select salt/hash for the GUI


# ---------- Validators  ----------

def is_valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def is_valid_username(username):
    """3-20 characters: letters, numbers and underscores only."""
    return re.fullmatch(r"[A-Za-z0-9_]{3,20}", username) is not None


def mask_email(email):
    """juan.cruz@example.com -> ju***@example.com"""
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"


# ---------- Password hashing ----------

def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, hash_hex):
    _, digest = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, hash_hex)


# ---------- Lookups ----------

def username_taken(username):
    with connection() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE username = ?",
                           (username,)).fetchone()
    return row is not None


def email_taken(email):
    with connection() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE email = ?",
                           (email,)).fetchone()
    return row is not None


def get_user(user_id):
    with connection() as conn:
        row = conn.execute(f"SELECT {PUBLIC_COLUMNS} FROM users WHERE id = ?",
                           (user_id,)).fetchone()
    return dict(row) if row else None


def find_user_by_login(login):
    """The account for a username OR an email (any case), or None.

    A username can never contain "@" and an email always does, so one text
    can only ever match one account. Used by "Forgot username or password"."""
    login = (login or "").strip()
    if not login:
        return None
    with connection() as conn:
        row = conn.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM users WHERE username = ? OR email = ?",
            (login, login)).fetchone()
    return dict(row) if row else None


# ---------- Register and login ----------

def register_user(username, full_name, email, password):
    """Create the account and return its id. Raises ValueError if invalid."""
    username, full_name, email = username.strip(), full_name.strip(), email.strip()
    if not (username and full_name and email and password):
        raise ValueError("Please fill in all fields.")
    if not is_valid_email(email):
        raise ValueError("Please enter a valid email address.")
    if not is_valid_username(username):
        raise ValueError("Username must be 3-20 letters, numbers or underscores.")
    if len(password) < MIN_PASSWORD:
        raise ValueError("Password must be at least 8 characters.")
    if username_taken(username):
        raise ValueError("That username is already taken.")
    if email_taken(email):
        raise ValueError("That email is already registered.")

    salt, pw_hash = hash_password(password)
    try:
        with connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, full_name, email, salt, password_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, full_name, email, salt, pw_hash))
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("That username or email is already taken.")


def verify_login(login, password):
    """Log in with a username OR an email. Return the user dict, or None.

    Wrong user and wrong password look the same."""
    login = login.strip()
    with connection() as conn:
        row = conn.execute(
            f"SELECT {PUBLIC_COLUMNS}, salt, password_hash FROM users "
            "WHERE username = ? OR email = ?",
            (login, login)).fetchone()
    if row is None:
        hash_password(password)
        return None
    if not verify_password(password, row["salt"], row["password_hash"]):
        return None
    return {key: row[key] for key in ("id", "username", "full_name", "email")}


# ---------- Profile changes ----------

def update_name(user_id, name):
    name = name.strip()
    if not name:
        raise ValueError("Name cannot be empty.")
    with connection() as conn:
        conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (name, user_id))


def update_email(user_id, email):
    email = email.strip()
    if not is_valid_email(email):
        raise ValueError("Please enter a valid email address.")
    with connection() as conn:
        taken = conn.execute("SELECT 1 FROM users WHERE email = ? AND id != ?",
                             (email, user_id)).fetchone()
        if taken:
            raise ValueError("That email is already registered.")
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))


def update_password(user_id, old_password, new_password):
    with connection() as conn:
        row = conn.execute("SELECT salt, password_hash FROM users WHERE id = ?",
                           (user_id,)).fetchone()
        if row is None or not verify_password(
                old_password, row["salt"], row["password_hash"]):
            raise ValueError("Current password is incorrect.")
        if len(new_password) < MIN_PASSWORD:
            raise ValueError("Password must be at least 8 characters.")
        if new_password == old_password:
            raise ValueError("Choose a different password.")
        salt, pw_hash = hash_password(new_password)
        conn.execute("UPDATE users SET salt = ?, password_hash = ? WHERE id = ?",
                     (salt, pw_hash, user_id))


def reset_password(user_id, new_password):
    """Set a new password WITHOUT the old one (the "forgot password" flow).

    Only call this after the person proved they own the account's email with
    the one-time code. Raises ValueError if the password is invalid."""
    if len(new_password) < MIN_PASSWORD:
        raise ValueError("Password must be at least 8 characters.")
    salt, pw_hash = hash_password(new_password)
    with connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET salt = ?, password_hash = ? WHERE id = ?",
            (salt, pw_hash, user_id))
        if cursor.rowcount == 0:
            raise ValueError("That account no longer exists.")