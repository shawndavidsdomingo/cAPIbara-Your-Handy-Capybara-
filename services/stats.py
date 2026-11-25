"""Dashboard totals.

Everything is counted with SQL, per user.
"""
from datetime import date, timedelta

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


def activity_by_day(user_id, days=7):
    """What the user did on each of the last `days` days (today last), for the charts.

    [{"date": "2026-11-24", "emails": 1, "sms": 0, "links": 2, "gens": 0}, ...]
    Days with no activity are included as zeros. Dates are in the computer's own
    time zone (SQLite stores UTC)."""
    first = date.today() - timedelta(days=days - 1)
    rows = {(first + timedelta(days=i)).isoformat():
            {"emails": 0, "sms": 0, "links": 0, "gens": 0} for i in range(days)}
    queries = (
        "SELECT date(sent_at, 'localtime'), "
        "CASE kind WHEN 'Email' THEN 'emails' ELSE 'sms' END, COUNT(*) "
        "FROM messages WHERE user_id = ? AND status = 'SENT' AND sent_at IS NOT NULL "
        "GROUP BY 1, 2",
        "SELECT date(created_at, 'localtime'), 'links', COUNT(*) "
        "FROM links WHERE user_id = ? GROUP BY 1, 2",
        "SELECT date(created_at, 'localtime'), 'gens', COUNT(*) "
        "FROM fake_generations WHERE user_id = ? GROUP BY 1, 2",
    )
    with connection() as conn:
        for sql in queries:
            for day, key, total in conn.execute(sql, (user_id,)).fetchall():
                if day in rows:
                    rows[day][key] += total
    return [{"date": day, **counts} for day, counts in rows.items()]