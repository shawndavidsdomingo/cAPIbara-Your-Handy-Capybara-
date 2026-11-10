"""SQLite connection helper and schema (guide section 2).

capibara.db is created next to this file on first launch by init_db().
Foreign keys are switched on for every connection.
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capibara.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    salt          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection():
    """Commit on success, roll back on error, and always close."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript(SCHEMA)
