"""SQLite connection helper and schema (guide section 2).

capibara.db is created next to the app (the project's top folder, or the .exe) on first launch by init_db().
Foreign keys are switched on for every connection.
"""
import os
import sqlite3
from contextlib import contextmanager

from core.paths import app_folder

DB_PATH = os.path.join(app_folder(), "capibara.db")

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

CREATE TABLE IF NOT EXISTS links (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    short_url    TEXT NOT NULL,
    original_url TEXT NOT NULL,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_links_user ON links(user_id);

CREATE TABLE IF NOT EXISTS link_clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id    INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    clicked_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_clicks_link ON link_clicks(link_id);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    kind       TEXT NOT NULL CHECK (kind IN ('SMS', 'Email')),
    recipient  TEXT NOT NULL DEFAULT '',
    subject    TEXT,
    body       TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL CHECK (status IN ('DRAFT', 'SENT', 'FAILED')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    sent_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, kind, status);

CREATE TABLE IF NOT EXISTS fake_generations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    number     INTEGER NOT NULL,              -- the "3" in "Gen 3", per user
    fields     TEXT NOT NULL,                 -- JSON list of the fields picked
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fakegen_user ON fake_generations(user_id);

CREATE TABLE IF NOT EXISTS fake_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id INTEGER NOT NULL REFERENCES fake_generations(id) ON DELETE CASCADE,
    data          TEXT NOT NULL               -- JSON object: field key -> value
);
CREATE INDEX IF NOT EXISTS idx_fakerec_gen ON fake_records(generation_id);

CREATE TABLE IF NOT EXISTS contacts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    name       TEXT NOT NULL,
    mobile     TEXT NOT NULL DEFAULT '',      -- 09XXXXXXXXX, or empty
    email      TEXT NOT NULL DEFAULT '',      -- or empty (one of the two is required)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CHECK (mobile != '' OR email != '')
);
CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);
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