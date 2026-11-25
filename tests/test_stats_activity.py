"""stats.activity_by_day: the numbers behind the dashboard bar chart."""
from datetime import date, timedelta

import pytest

from core import db
from services import stats


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    with db.connection() as c:
        c.execute("INSERT INTO users (username, full_name, email, salt, password_hash) "
                  "VALUES ('a', 'A', 'a@x.com', 's', 'h')")
        c.execute("INSERT INTO users (username, full_name, email, salt, password_hash) "
                  "VALUES ('b', 'B', 'b@x.com', 's', 'h')")
    return db


def add_message(user, kind, status, when):
    with db.connection() as c:
        c.execute("INSERT INTO messages (user_id, kind, recipient, body, status, sent_at) "
                  "VALUES (?, ?, 'x', 'b', ?, " + when + ")", (user, kind, status))


def test_empty_user_gets_seven_zero_days(conn):
    days = stats.activity_by_day(1, 7)
    assert len(days) == 7
    assert days[-1]["date"] == date.today().isoformat()
    assert days[0]["date"] == (date.today() - timedelta(days=6)).isoformat()
    assert all(d["emails"] == d["sms"] == d["links"] == d["gens"] == 0 for d in days)


def test_counts_go_to_the_right_day_and_kind(conn):
    add_message(1, "Email", "SENT", "datetime('now')")
    add_message(1, "Email", "SENT", "datetime('now')")
    add_message(1, "SMS", "SENT", "datetime('now')")
    add_message(1, "SMS", "SENT", "datetime('now', '-3 days')")
    with db.connection() as c:
        c.execute("INSERT INTO links (user_id, short_url, original_url) VALUES (1, 's', 'o')")
        c.execute("INSERT INTO fake_generations (user_id, number, fields) VALUES (1, 1, '[]')")
    days = {d["date"]: d for d in stats.activity_by_day(1, 7)}
    today = days[date.today().isoformat()]
    assert (today["emails"], today["sms"], today["links"], today["gens"]) == (2, 1, 1, 1)
    earlier = days[(date.today() - timedelta(days=3)).isoformat()]
    assert (earlier["emails"], earlier["sms"]) == (0, 1)


def test_ignores_drafts_old_days_and_other_users(conn):
    add_message(1, "Email", "DRAFT", "NULL")
    add_message(1, "Email", "SENT", "datetime('now', '-30 days')")
    add_message(2, "Email", "SENT", "datetime('now')")
    days = stats.activity_by_day(1, 7)
    assert sum(d["emails"] for d in days) == 0
    assert sum(d["emails"] for d in stats.activity_by_day(2, 7)) == 1
