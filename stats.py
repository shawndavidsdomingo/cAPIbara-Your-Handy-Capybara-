"""Dashboard totals.

Links are counted with SQL (Sprint 2). Emails, texts and fake-data generations
are still in-memory counters until Sprints 3 and 4 give them tables.
"""
from db import connection

_data = {"emails": 0, "sms": 0, "generations": []}


def reset():
    _data.update(emails=0, sms=0, generations=[])


def record_sent(kind):                 # kind is "SMS" or "Email"
    _data["sms" if kind == "SMS" else "emails"] += 1


def record_generation(name):           # e.g. "Gen 3"
    _data["generations"].append(name)


def count_links(user_id):
    sql = "SELECT COUNT(*) FROM links WHERE user_id = ?"
    with connection() as conn:
        return conn.execute(sql, (user_id,)).fetchone()[0]


def get():
    return _data
