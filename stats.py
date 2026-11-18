"""Dashboard totals.

Links, emails and texts are counted with SQL. Fake-data generations are still
an in-memory list until Sprint 4 gives them a table.
"""
from db import connection

_data = {"generations": []}


def reset():
    _data.update(generations=[])


def record_generation(name):           # e.g. "Gen 3"
    _data["generations"].append(name)


def count_links(user_id):
    sql = "SELECT COUNT(*) FROM links WHERE user_id = ?"
    with connection() as conn:
        return conn.execute(sql, (user_id,)).fetchone()[0]


def _count_sent(user_id, kind):
    sql = ("SELECT COUNT(*) FROM messages "
           "WHERE user_id = ? AND kind = ? AND status = 'SENT'")
    with connection() as conn:
        return conn.execute(sql, (user_id, kind)).fetchone()[0]


def count_emails(user_id):
    return _count_sent(user_id, "Email")


def count_sms(user_id):
    return _count_sent(user_id, "SMS")


def get():
    return _data