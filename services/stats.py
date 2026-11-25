"""Dashboard totals.

Everything is counted with SQL, per user.
"""
from core.db import connection


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


def count_generations(user_id):
    sql = "SELECT COUNT(*) FROM fake_generations WHERE user_id = ?"
    with connection() as conn:
        return conn.execute(sql, (user_id,)).fetchone()[0]


def generation_names(user_id):
    """["Gen 1", "Gen 2", ...] for the dashboard."""
    sql = "SELECT number FROM fake_generations WHERE user_id = ? ORDER BY id"
    with connection() as conn:
        return [f"Gen {row[0]}" for row in conn.execute(sql, (user_id,)).fetchall()]